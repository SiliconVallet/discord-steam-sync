import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import re
import os
from dotenv import load_dotenv


# Charger les variables d'environnement
load_dotenv()

class EventSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.steam_url = os.getenv('STEAM_GROUP_URL')
        self.guild_id = int(os.getenv('DISCORD_GUILD_ID'))
        # self.sync_events.start()
        
        
        # Vérifier que les variables obligatoires sont présentes
        if not self.steam_url:
            raise ValueError("L'URL du groupe Steam n'a pas été trouvée dans les variables d'environnement")
        if not self.guild_id:
            raise ValueError("L'ID du serveur Discord n'a pas été trouvé dans les variables d'environnement")

    def get_time_parts(self, time_str):
        """Convert time string to hour and minute
        Handles formats:
        - 20h30
        - 8:30 PM
        - 8:30 AM
        """
        time_str = time_str.lower().strip()
        
        # Format 20h30
        if 'h' in time_str:
            hour, minute = time_str.replace('h', ':').split(':')
            return int(hour), int(minute)
        
        # Format avec AM/PM
        if 'am' in time_str or 'pm' in time_str:
            # Enlever AM/PM et récupérer l'indicateur
            is_pm = 'pm' in time_str
            clean_time = time_str.replace('am', '').replace('pm', '').strip()
            
            # Séparer heures et minutes
            if ':' in clean_time:
                hour, minute = map(int, clean_time.split(':'))
            else:
                # Si pas de minutes (ex: "8 PM")
                hour = int(clean_time)
                minute = 0
                
            # Ajuster pour PM
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
                
            return hour, minute
        
        # Format simple HH:MM
        if ':' in time_str:
            hour, minute = map(int, time_str.split(':'))
            return hour, minute
            
        # Si juste une heure
        return int(time_str), 0

    def get_steam_events(self):
        if not self.steam_url.endswith('/events'):
            group_url = self.steam_url.rstrip('/') + '/events'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(group_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            future_events = []
            future_events_div = soup.find('div', id='eventListing')
            if not future_events_div:
                return []
                
            paris_tz = pytz.timezone('Europe/Paris')
                
            month_str = soup.find('p', id='futureEventsHeader').text.strip()
            month_parts = month_str.split()
            month_num = datetime.strptime(month_parts[0], "%B").month
            year = int(month_parts[1])
                
            event_blocks = future_events_div.find_all('div', class_='eventBlock')
            
            for block in event_blocks:
                date_block = block.find('div', class_='eventDateBlock')
                if not date_block:
                    continue
                    
                day = date_block.find('span').text.split()[1]
                time_elem = date_block.find('span', class_='eventDateTime')
                if not time_elem:
                    continue

                time_str = time_elem.text.strip().lower()
                print(f"Time string found: {time_str}")
                
                is_pm = 'pm' in time_str
                clean_time = time_str.replace('am', '').replace('pm', '').strip()
                
                hour, minute = map(int, clean_time.split(':'))
                
                if is_pm and hour != 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0

                naive_date = datetime(year, month_num, int(day), hour, minute)
                pt_date = naive_date + timedelta(hours=9)
                    
                print(f"Converted time (Paris): {pt_date.hour}:{pt_date.minute}")
                
                event_date = paris_tz.localize(pt_date)
                
                today = datetime.now(paris_tz)
                if event_date.day < today.day and event_date.month == today.month:
                    if event_date.month == 12:
                        event_date = event_date.replace(year=event_date.year + 1, month=1)
                    else:
                        event_date = event_date.replace(month=event_date.month + 1)
                
                title = block.find('a', class_='headlineLink').text
                event_id = block.get('id').split('_')[0]
                event_url = f"{self.steam_url}/events/{event_id}"
                
                print(f"Récupération des détails de l'événement: {event_url}")
                description, image_url = self.get_event_details(event_url)
                
                event = {
                    'title': title,
                    'date': event_date.strftime("%d %B %Y à %H:%M"),
                    'raw_date': event_date,
                    'url': event_url,
                    'description': description,
                    'image_url': image_url
                }
                print(f"Event parsed: {event['title']} at {event['date']} ({event_date.tzinfo})")
                future_events.append(event)
                
            return future_events
            
        except Exception as e:
            print(f"Erreur lors de la récupération des événements Steam: {e}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            return []

    def get_event_details(self, event_url):
        """Récupère les détails d'un événement Steam (description et image)"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(event_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            description = ""
            image_url = None
            
            # Récupérer la description depuis eventContent
            event_content = soup.find('div', class_='eventContent')
            if event_content:
                description_elem = event_content.find('p')
                if description_elem:
                    # Récupérer le HTML brut et remplacer les <br> par des sauts de ligne
                    html_content = str(description_elem)
                    # Remplacer les <br> et <br/> par des sauts de ligne
                    html_content = html_content.replace('<br>', '\n').replace('<br/>', '\n')
                    # Supprimer les balises restantes
                    soup_text = BeautifulSoup(html_content, 'html.parser')
                    description = soup_text.get_text()
                    # Nettoyer les sauts de ligne multiples
                    description = '\n'.join(line.strip() for line in description.split('\n') if line.strip())
                    print(f"HTML brut: {html_content}")
                    print(f"Description trouvée: {description}")
            
            # Récupérer l'image depuis eventLogo
            event_logo = soup.find('div', class_='eventLogo')
            if event_logo:
                game_logo = event_logo.find('div', class_='gameLogo')
                if game_logo:
                    img = game_logo.find('img')
                    if img and 'src' in img.attrs:
                        image_url = img['src']
                        print(f"Image URL trouvée: {image_url}")
            
            return description, image_url
            
        except Exception as e:
            print(f"Erreur lors de la récupération des détails de l'événement: {e}")
            return "", None


    # @tasks.loop(minutes=30)
    async def sync_events(self):
        print("Début de la synchronisation...")
        paris_tz = pytz.timezone('Europe/Paris')
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            print(f"Impossible de trouver le serveur avec l'ID {self.guild_id}")
            return

        # Récupérer les événements Steam actuels
        steam_events = self.get_steam_events()
        print(f"Événements Steam trouvés: {len(steam_events)}")
        
        try:
            # Récupérer tous les événements Discord
            discord_events = await guild.fetch_scheduled_events()
            # Créer un dictionnaire des événements Discord basé sur l'ID Steam dans la description
            discord_event_dict = {}
            for event in discord_events:
                if event.description:
                    # Chercher l'URL Steam dans la description
                    if "Event Steam: " in event.description:
                        steam_url = event.description.split("Event Steam: ")[1].strip()
                        # Extraire l'ID Steam de l'URL
                        steam_id = steam_url.split('/')[-1]
                        discord_event_dict[steam_id] = event
            
            print(f"Événements Discord existants: {len(discord_event_dict)}")

            # Créer un set des IDs Steam actuels
            current_steam_ids = {event['url'].split('/')[-1] for event in steam_events}
            
            # Vérifier les événements Discord à supprimer
            for steam_id, discord_event in discord_event_dict.items():
                if steam_id not in current_steam_ids:
                    print(f"Suppression de l'événement Discord: {discord_event.name} (Steam ID: {steam_id})")
                    try:
                        await discord_event.delete()
                        print(f"Événement supprimé avec succès: {discord_event.name}")
                    except Exception as e:
                        print(f"Erreur lors de la suppression de l'événement {discord_event.name}: {e}")
            
        except Exception as e:
            print(f"Erreur lors de la récupération des événements Discord: {e}")
            return

        # Mise à jour et création des événements
        for steam_event in steam_events:
            try:
                # Extraire l'ID Steam de l'URL
                steam_id = steam_event['url'].split('/')[-1]
                print(f"Traitement de l'événement Steam ID: {steam_id}")
                
                # Préparer la description avec l'URL Steam et la description
                full_description = f"{steam_event['description']}\n\nEvent Steam: {steam_event['url']}"
                
                # Préparer l'image si disponible
                image_bytes = None
                if steam_event['image_url']:
                    try:
                        image_response = requests.get(steam_event['image_url'])
                        if image_response.status_code == 200:
                            image_bytes = image_response.content
                            print(f"Image téléchargée avec succès: {steam_event['image_url']}")
                    except Exception as e:
                        print(f"Erreur lors de la récupération de l'image: {e}")
                
                if steam_id in discord_event_dict:
                    discord_event = discord_event_dict[steam_id]
                    steam_time = steam_event['raw_date']
                    discord_time = discord_event.start_time.astimezone(paris_tz)
                    
                    print(f"Comparaison des dates/heures pour {steam_event['title']}:")
                    print(f"Steam: {steam_time.strftime('%Y-%m-%d %H:%M')} ({steam_time.tzinfo})")
                    print(f"Discord: {discord_time.strftime('%Y-%m-%d %H:%M')} ({discord_time.tzinfo})")
                    
                    # Vérifier si la date ou l'heure a changé
                    date_changed = (
                        steam_time.year != discord_time.year or
                        steam_time.month != discord_time.month or
                        steam_time.day != discord_time.day or
                        steam_time.hour != discord_time.hour or
                        steam_time.minute != discord_time.minute
                    )
                    
                    if (date_changed or 
                        discord_event.description != full_description or
                        discord_event.name != steam_event['title']):
                        
                        if date_changed:
                            print(f"Date/heure modifiée pour {steam_event['title']}:")
                            print(f"Ancienne date: {discord_time.strftime('%Y-%m-%d %H:%M')}")
                            print(f"Nouvelle date: {steam_time.strftime('%Y-%m-%d %H:%M')}")
                        
                        print(f"Mise à jour de l'événement: {steam_event['title']}")
                        
                        try:
                            update_data = {
                                'name': steam_event['title'],
                                'start_time': steam_time,
                                'end_time': steam_time + timedelta(hours=2),
                                'description': full_description
                            }
                            if image_bytes:
                                update_data['image'] = image_bytes
                            
                            await discord_event.edit(**update_data)
                            print(f"Événement mis à jour avec succès: {steam_event['title']}")
                        except Exception as e:
                            print(f"Erreur lors de la mise à jour de l'événement: {e}")
                    else:
                        print(f"Pas de changement nécessaire pour: {steam_event['title']}")
                        
                else:
                    print(f"Création de l'événement: {steam_event['title']}")
                    try:
                        create_data = {
                            'name': steam_event['title'],
                            'description': full_description,
                            'start_time': steam_event['raw_date'],
                            'end_time': steam_event['raw_date'] + timedelta(hours=2),
                            'location': steam_event['url'],
                            'privacy_level': discord.PrivacyLevel.guild_only,
                            'entity_type': discord.EntityType.external
                        }
                        if image_bytes:
                            create_data['image'] = image_bytes
                        
                        await guild.create_scheduled_event(**create_data)
                        print(f"Événement créé avec succès: {steam_event['title']}")
                    except Exception as e:
                        print(f"Erreur lors de la création de l'événement: {e}")
                        try:
                            # Essayer sans l'image
                            create_data.pop('image', None)
                            await guild.create_scheduled_event(**create_data)
                            print(f"Événement créé avec succès (sans image): {steam_event['title']}")
                        except Exception as e:
                            print(f"Erreur lors de la création de l'événement sans image: {e}")
                    
            except Exception as e:
                print(f"Erreur lors du traitement de l'événement {steam_event['title']}: {e}")
                import traceback
                print(traceback.format_exc())
        await self.bot.close()


# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True
intents.guild_scheduled_events = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que: {bot.user.name}')
    # Lancer la synchro directement
    cog = EventSync(bot)
    await bot.add_cog(cog)
    await cog.sync_events()

if __name__ == "__main__":
    # Vérifier que toutes les variables d'environnement sont présentes
    required_env_vars = {
        'DISCORD_TOKEN': 'Token Discord',
        'DISCORD_GUILD_ID': 'ID du serveur Discord',
        'STEAM_GROUP_URL': 'URL du groupe Steam'
    }
    
    missing_vars = []
    for var, name in required_env_vars.items():
        if not os.getenv(var):
            missing_vars.append(name)
    
    if missing_vars:
        raise ValueError(f"Variables d'environnement manquantes : {', '.join(missing_vars)}")
    
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)