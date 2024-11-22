import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import re
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import traceback
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(f"{self.steam_url}/events")
            
            future_events = []
            
            # Premier mois
            # initial_month = driver.find_element(By.ID, 'futureEventsHeader').text
            # print(f"Mois actuel: {initial_month}")
            # future_events.extend(self._parse_events_page(driver.page_source))
            
            # Mois suivant
            next_buttons = driver.find_elements(By.CSS_SELECTOR, "a[href*='javascript:calChangeMonth']")
            next_month_button = None    
            for button in next_buttons:
                img = button.find_element(By.TAG_NAME, 'img')
                if 'monthForwardOn' in img.get_attribute('src'):
                    next_month_button = button
                    break
            
            if next_month_button:
                old_content = driver.page_source
                driver.execute_script("arguments[0].click();", next_month_button)
                
                WebDriverWait(driver, 10).until(
                    lambda d: d.page_source != old_content
                )
                
                time.sleep(1)
                
                new_month = driver.find_element(By.ID, 'futureEventsHeader').text
                print(f"Mois suivant: {new_month}")
                future_events.extend(self._parse_events_page(driver.page_source))

                # Recharger les boutons pour le mois précédent
                next_buttons = driver.find_elements(By.CSS_SELECTOR, "a[href*='javascript:calChangeMonth']")
                prev_month_button = None
                for button in next_buttons:
                    img = button.find_element(By.TAG_NAME, 'img')
                    if 'monthBackOn' in img.get_attribute('src'):
                        prev_month_button = button
                        break

                if prev_month_button:
                    old_content = driver.page_source
                    driver.execute_script("arguments[0].click();", prev_month_button)
                    
                    WebDriverWait(driver, 10).until(
                        lambda d: d.page_source != old_content
                    )
                    
                    time.sleep(1)
                    
                    current_month = driver.find_element(By.ID, 'futureEventsHeader').text
                    print(f"Mois précédent: {current_month}")
                    future_events.extend(self._parse_events_page(driver.page_source))
            
            driver.quit()
            return future_events
            
        except Exception as e:
            print(f"Erreur: {e}", flush=True)
            traceback.print_exc()
            if 'driver' in locals():
                driver.quit()
            return []

    def get_event_details(self, event_url):
        """Récupère les détails d'un événement Steam (description et image)"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'timezone': 'Europe/Paris'
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
                    # print(f"HTML brut: {html_content}")
                    # print(f"Description trouvée: {description}")
            
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

    def _parse_events_page(self, html_content):
        events = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        future_events_div = soup.find('div', id='eventListing')
        if not future_events_div:
            return events
                
        paris_tz = pytz.timezone('Europe/Paris')
        
        MONTHS = {
            # Français
            'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
            'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
            'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
            # English
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        month_str = soup.find('p', id='futureEventsHeader')
        if not month_str:
            print("En-tête du mois non trouvé")
            return events
        
        month_parts = month_str.text.strip().split()
        if len(month_parts) < 2:
            print("Format d'en-tête du mois invalide")
            return events
            
        month_name = month_parts[0].lower()
        month_num = MONTHS.get(month_name)
        if not month_num:
            print(f"Mois non reconnu: {month_name}")
            return events
        year = int(month_parts[1])
        
        event_blocks = future_events_div.find_all('div', class_='eventBlock')
        
        for block in event_blocks:
            try:
                date_block = block.find('div', class_='eventDateBlock')
                if not date_block:
                    continue
                    
                day = date_block.find('span').text.split()[1]
                time_elem = date_block.find('span', class_='eventDateTime')
                if not time_elem:
                    continue

                time_str = time_elem.text.strip().lower()
                print (time_str)
                # Gestion du format français (11h00)
                if 'h' in time_str:
                    hour, minute = time_str.replace('h', ':').split(':')
                    hour = int(hour)
                    minute = int(minute)
                else:
                    # Gestion du format AM/PM
                    is_pm = 'pm' in time_str
                    clean_time = time_str.replace('am', '').replace('pm', '').strip()
                    hour, minute = map(int, clean_time.split(':'))
                    if is_pm and hour != 12:
                        hour += 12
                    elif not is_pm and hour == 12:
                        hour = 0

                # Créer d'abord la date en UTC
                naive_date = datetime(year, month_num, int(day), hour, minute)
                utc_tz = pytz.UTC
                
                # Considérer que l'heure Steam est en UTC+1 (CET)
                cet_tz = pytz.timezone('Europe/Paris')
                event_date = cet_tz.localize(naive_date)
                
                # Convertir en UTC pour Discord
                utc_date = event_date.astimezone(utc_tz)

                title = block.find('a', class_='headlineLink').text
                event_id = block.get('id').split('_')[0]
                event_url = f"{self.steam_url}/events/{event_id}"
                
                description, image_url = self.get_event_details(event_url)
                
                event = {
                    'title': title,
                    'date': event_date.strftime("%d %B %Y à %H:%M"),
                    'raw_date': utc_date,
                    'url': event_url,
                    'description': description,
                    'image_url': image_url
                }
                
                events.append(event)
                
            except Exception as e:
                print(f"Error parsing event block: {e}")
                continue
        
        return events

    # @tasks.loop(minutes=30)
    async def sync_events(self):
        print("Début de la synchronisation...")
        paris_tz = pytz.timezone('Europe/Paris')
        current_time = datetime.now(paris_tz)
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        steam_events = self.get_steam_events()
        
        try:
            discord_events = await guild.fetch_scheduled_events()
            discord_event_dict = {}
            for event in discord_events:
                if event.description and "Event Steam: " in event.description:
                    steam_url = event.description.split("Event Steam: ")[1].strip()
                    steam_id = steam_url.split('/')[-1]
                    discord_event_dict[steam_id] = event

            for steam_event in steam_events:
                print(steam_event['raw_date'])
                steam_time = steam_event['raw_date'].astimezone(paris_tz)
                
                if steam_time <= current_time:
                    continue
                
                image_bytes = None
                if steam_event['image_url']:
                    try:
                        image_response = requests.get(steam_event['image_url'])
                        if image_response.status_code == 200:
                            image_bytes = image_response.content
                    except Exception as e:
                        print(f"Erreur image: {e}")
                
                event_data = {
                    'name': steam_event['title'],
                    'description': f"{steam_event['description']}\n\nEvent Steam: {steam_event['url']}",
                    'start_time': steam_time,
                    'end_time': steam_time + timedelta(hours=2),
                    'location': "Discord FRT",
                    'privacy_level': discord.PrivacyLevel.guild_only,
                    'entity_type': discord.EntityType.external
                }
                
                if image_bytes:
                    event_data['image'] = image_bytes
                
                steam_id = steam_event['url'].split('/')[-1]
                
                if steam_id in discord_event_dict:
                    await discord_event_dict[steam_id].edit(**event_data)
                else:
                    await guild.create_scheduled_event(**event_data)
                    
        except Exception as e:
            print(f"Erreur: {e}")
            traceback.print_exc()
        
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