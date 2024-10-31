import discord
from discord.ext import tasks
from discord_slash import SlashCommand, SlashContext
from datetime import datetime, timedelta
import os

with open('/run/secrets/bot_token') as f:
    BOT_TOKEN = f.read().strip()
with open('/run/secrets/channel_id') as f:
    CHANNEL_ID = int(f.read().strip())

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)
slash = SlashCommand(bot, sync_commands=True)

role_weights = {
    "Squire": 2,
    "Knight": 3,
    "Paladin": 4,
    "Champion": 5
}

votes = {}
vote_end_times = {}

@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user}')
    check_votes.start()

@slash.slash(name="start_vote", description="Démarre un vote avec des options et des images", options=[
    {
        "name": "duration",
        "description": "Durée du vote en secondes",
        "type": 4,  # INTEGER
        "required": True
    },
    {
        "name": "options",
        "description": "Options de vote et URL des images (option1 url1 option2 url2 ...)",
        "type": 3,  # STRING
        "required": True
    }
])
async def _start_vote(ctx: SlashContext, duration: int, options: str):
    options_with_urls = options.split()
    
    if len(options_with_urls) % 2 != 0:
        await ctx.send("Assurez-vous de fournir une paire d'options et d'URL d'images pour chaque option.", hidden=True)
        return

    embed = discord.Embed(title="Votez pour votre favori", description="Réagissez avec l'emoji correspondant pour voter.", color=0x00ff00)

    for i in range(0, len(options_with_urls), 2):
        option = options_with_urls[i]
        image_url = options_with_urls[i+1]
        emoji = chr(0x1F1E6 + (i // 2))
        embed.add_field(name=option, value=f"Réagissez avec {emoji}", inline=False)
        embed.set_image(url=image_url)

    vote_message = await ctx.send(embed=embed)

    for i in range(len(options_with_urls) // 2):
        emoji = chr(0x1F1E6 + i)
        await vote_message.add_reaction(emoji)

    votes[vote_message.id] = {}
    vote_end_times[vote_message.id] = datetime.utcnow() + timedelta(seconds=duration)
    await ctx.send(f"Le vote se terminera dans {duration} secondes.", hidden=True)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.message.id not in votes:
        return

    role = next((role.name for role in user.roles if role.name in role_weights), None)
    weight = role_weights.get(role, 1)

    option_index = ord(str(reaction.emoji)[-1]) - 0x1F1E6
    if 0 <= option_index < len(votes[reaction.message.id]):
        option = list(votes[reaction.message.id])[option_index]
        votes[reaction.message.id][user.id] = (option, weight)
        await reaction.message.channel.send(f'{user.mention} a voté pour {option} avec un poids de {weight}.')

        results = {}
        for vote_option, vote_weight in votes[reaction.message.id].values():
            if vote_option in results:
                results[vote_option] += vote_weight
            else:
                results[vote_option] = vote_weight

        results_message = "\n".join([f'{vote_option}: {vote_weight} votes' for vote_option, vote_weight in results.items()])
        await reaction.message.channel.send(f'Résultats actuels des votes:\n{results_message}')

@tasks.loop(seconds=10)
async def check_votes():
    now = datetime.utcnow()
    ended_votes = [msg_id for msg_id, end_time in vote_end_times.items() if end_time <= now]

    for msg_id in ended_votes:
        vote_message = await bot.get_channel(CHANNEL_ID).fetch_message(msg_id)
        results = {}
        for option, weight in votes[msg_id].values():
            if option in results:
                results[option] += weight
            else:
                results[option] = weight

        results_message = "\n".join([f'{option}: {weight} votes' for option, weight in results.items()])
        await vote_message.channel.send(f'Le vote est terminé! Résultats:\n{results_message}')

        for user_id in votes[msg_id].keys():
            user = await bot.fetch_user(user_id)
            await user.send(f'Le vote est terminé! Résultats:\n{results_message}')

        del votes[msg_id]
        del vote_end_times[msg_id]

bot.run(BOT_TOKEN)
