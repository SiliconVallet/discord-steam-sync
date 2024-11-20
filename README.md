# Discord Steam Event Sync Bot

Bot Discord qui synchronise les événements entre un groupe Steam et un serveur Discord.

## Configuration

### Variables d'environnement requises

- `DISCORD_TOKEN` : Le token de votre bot Discord
- `DISCORD_GUILD_ID` : L'ID de votre serveur Discord
- `STEAM_GROUP_URL` : L'URL de votre groupe Steam

### Configuration locale

Créez un fichier `.env` à la racine du projet :
```
DISCORD_TOKEN=votre_token_discord
DISCORD_GUILD_ID=votre_id_serveur
STEAM_GROUP_URL=votre_url_groupe_steam
```

### Configuration GitHub Actions

Ajoutez les secrets suivants dans votre repository GitHub :
1. `DISCORD_TOKEN`
2. `DISCORD_GUILD_ID`
3. `STEAM_GROUP_URL`

## Installation locale

```bash
# Créer un environnement virtuel
python -m venv venv

# Activer l'environnement virtuel
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer le bot
python bot.py
```

## Planification

Le bot s'exécute automatiquement une fois par jour à 8h UTC via GitHub Actions.