import os
from discord.ext import commands
import asyncpg

from urllib.parse import urlparse
import requests_async as requests
from bs4 import BeautifulSoup
import json
from base64 import b64encode

from random import randint

bot = commands.Bot(command_prefix="!")
TOKEN = os.getenv("DISCORD_TOKEN")

DATABASE_URL = os.environ['DATABASE_URL']
ROWS_PER_PAGE = 10

SPOTIFY_CLIENT_ID = os.environ['SPOTIFY_CLIENT_ID']
SPOTIFY_CLIENT_SECRET = os.environ['SPOTIFY_CLIENT_SECRET']

GRAPHQL_SERVER = "127.0.0.1:5000/graphql"


async def query_graphql(payload):
    payload = GRAPHQL_SERVER + '?query=' + payload
    if payload[:8] == 'mutation':
        res = await requests.post(payload)
    else:
        res = await requests.get(payload)
    return json.loads(res.text)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}({bot.user.id})")


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


async def get_or_create_user(ctx, conn, discord_id):
    username = await conn.fetchval(f"SELECT id FROM users WHERE discord_id = {discord_id}")
    if not username is None:
        return username
    msg = await ctx.send("You do not have an account. Create an account?")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    def check(reaction, user):
        return reaction.message.id == msg.id and user == ctx.message.author and str(reaction.emoji) in ['✅', '❌', ]

    try:
        reaction, _user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except:
        # timeout
        await msg.delete()
        return
    if str(reaction.emoji) == '❌':
        await msg.delete()
        return
    await ctx.send("Enter your username")

    def check_info(m):
        return m.author == ctx.message.author and m.content[0] != '!'

    username = await bot.wait_for('message', check=check_info)
    await conn.execute(f"INSERT INTO users(id, discord_id) VALUES ({username.content}, {discord_id})")
    await ctx.send(f"Registered new user {username.content}")
    return username.content


@bot.command()
async def stats(ctx):
    db_conn = await asyncpg.connect(DATABASE_URL)
    user = ctx.message.author
    user_row = await db_conn.fetchrow(f"SELECT * FROM users WHERE discord_id = {user.id}")
    if user_row is None:
        await ctx.send(f"user with discord id {user.id} does not exist")
    else:
        stats_string = "Here is your data:\n" + f"username: {user_row[0]}\n"
        if user_row[2]:
            stats_string += ":star: is admin\n"
        await ctx.send(stats_string)


@bot.command()
async def echo(ctx, *args):
    await ctx.send(args)


async def get_new_id(conn, table):
    while True:
        new_id = randint(1, (2 ** 31) - 1)
        existing = await conn.fetchval(
            f"SELECT id FROM {table} WHERE id = {new_id}")
        if existing is None:
            return new_id


@bot.command()
async def test_wait(ctx, *args):
    state = randint(0, 2 ** 32)
    await ctx.send(f"{state:x} {args}")

    def check(m):
        return m.author == ctx.message.author and m.content[0] != '!'

    msg = await bot.wait_for('message', check=check)
    await ctx.send(f"{state:x} {msg}")


@bot.command()
async def emoji(ctx):
    msg = await ctx.send("react to this message")

    def check(reaction, user):
        return reaction.message.id == msg.id and user == ctx.message.author

    try:
        reaction, _user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except:
        # timeout
        await msg.delete()
    else:
        await msg.delete()
        await ctx.send("`" + str(reaction.emoji) + "`\n" + f"{reaction.emoji.encode('ascii', 'namereplace')}")

# =========================
# song
# =========================


@bot.command(aliases=['addsong'])
async def add_song(ctx, link):
    conn = await asyncpg.connect(DATABASE_URL)
    song_id = await conn.fetchval(f"SELECT song_id FROM links WHERE link = '{link}'")
    if not song_id is None:
        await ctx.send(f"entry already exists:")
        await view_song(ctx, song_id)
        return

    parsed_url = urlparse(link)
    # try to fix if user forgot 'https://'
    if parsed_url.scheme == '':
        link = 'https://' + link
        parsed_url = urlparse(link)
    # detect link type
    if parsed_url.netloc in ['www.youtube.com', 'youtube.com', 'youtu.be', 'm.youtube.com']:
        info = await add_youtube(ctx, link)
        if info is None:
            return
        (song_name, artist_name) = info
        link_type = 'youtube'
    elif parsed_url.netloc in ['open.spotify.com']:
        path = parsed_url.path.split('/')
        if path[0] != '':
            await ctx.send("wtf?")
            return
        if path[1] == 'album':
            await ctx.send("Tou are trying to add an entire spotify album.\n" + "This action is not supported yet, please add songs one by one.")
            return
        elif path[1] == 'track':
            if len(path) > 3:
                await ctx.send("why is there some data after track id?\n" + "ping my developer please")
                return
            new_link = parsed_url._replace(
                netloc='api.spotify.com', path='/v1/tracks/' + path[2]).geturl()
            info = await add_spotify(ctx, new_link)
            if info is None:
                return
            (song_name, artist_name) = info
            link_type = 'spotify'
        else:
            await ctx.send("I don't recognize this kind of spotify link... :/" + "ping my dev please")
            return
    else:
        await ctx.send(
            "I don't recognize this link, can't parse it dude :/")
        return

    # ask user to fix the song_name and artist_name if needed
    wait_change_msg = await ctx.send("adding song...\n" + f"name: `{song_name}`\n" + f"artist: `{artist_name}`\n" + "confirm song info ✅, edit song info ❔, or cancel ❌")
    await wait_change_msg.add_reaction('✅')
    await wait_change_msg.add_reaction('❔')
    await wait_change_msg.add_reaction('❌')

    def check(reaction, user):
        return reaction.message.id == wait_change_msg.id and user == ctx.message.author and str(reaction.emoji) in ['✅', '❔', '❌', ]

    try:
        reaction, _user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except:
        # timeout
        await wait_change_msg.delete()
        return
    if str(reaction.emoji) == '✅':
        pass
    elif str(reaction.emoji) == '❔':
        # edit
        def check_info(m):
            return m.author == ctx.message.author and m.content[0] != '!'
        await ctx.send('Please enter the correct song name:')
        song_name_msg = await bot.wait_for('message', check=check_info)
        song_name = song_name_msg.content
        await ctx.send('Please enter the correct artist name:')
        artist_name_msg = await bot.wait_for('message', check=check_info)
        artist_name = artist_name_msg.content
    elif str(reaction.emoji) == '❌':
        await wait_change_msg.delete()
        return

    matching_song = await conn.fetchrow(
        f"SELECT id, name FROM songs WHERE name = ($1)", song_name)
    if matching_song is None:
        # add new song
        # ...but first find or create new artist
        matching_artist = await conn.fetchrow(
            f"SELECT id, name FROM artists WHERE name = ($1)", artist_name)
        if matching_artist is None:
            artist_id = await get_new_id(conn, 'artists')
            await conn.execute(
                f"INSERT INTO artists VALUES ({artist_id}, '{artist_name}', NULL)")
            await ctx.send(f"created new artist entry `{artist_id:x}`")
        else:
            artist_id = matching_artist[0]
            await ctx.send(f"found existing artist entry `{artist_id:x}`")

        # now actually add new song
        new_id = await get_new_id(conn, 'songs')
        await conn.execute(
            f"INSERT INTO songs(id, name, artist_ids) VALUES (($1), ($2), ($3))", new_id, song_name, [artist_id])
        msg = await ctx.send(f"created new song entry `{new_id:x}`")
        song_id = new_id
        await msg.add_reaction('🔢')
    else:
        song_id = matching_song['id']
        msg = await ctx.send(f"found song with same title: `{song_id:x}`, linking to that song")
        await msg.add_reaction('🔢')

    # TODO: move this somewhere else, this is a bit scuffed
    await conn.execute(f"INSERT INTO links VALUES (($1), ($2), ($3))", link, link_type, song_id)

    def check2(reaction, user):
        return reaction.message.id == msg.id and user == ctx.message.author and str(reaction.emoji) == '🔢'

    try:
        reaction, _user = await bot.wait_for('reaction_add', timeout=60.0, check=check2)
    except:
        await msg.remove_reaction('🔢', msg.author)
        return
    await rate_react(ctx, song_id)


async def add_youtube(ctx, link):
    print('adding youtube link', link)
    try:
        r = await requests.get(link)
        print(r.status_code)
        if r is None:
            await ctx.send("couldn't reach your link")
        soup = BeautifulSoup(r.text, 'html.parser')
        song_name = soup.find('meta', {'property': 'og:title'})['content']
        author_span = soup.find('span', {'itemprop': 'author'})
        author_name = author_span.find('link', {'itemprop': 'name'})['content']
        return (song_name, author_name)
    except Exception as e:
        await ctx.send("failed to parse your youtube link :/")
        await ctx.send(f"{e}")


async def add_spotify(ctx, link):
    print('adding spotify link', link)
    try:
        r = await requests.post('https://accounts.spotify.com/api/token',
                                data={'grant_type': 'client_credentials'},
                                headers={
                                    'Authorization': 'Basic ' + b64encode((SPOTIFY_CLIENT_ID + ':' + SPOTIFY_CLIENT_SECRET).encode()).decode()}
                                )
        print('spotify authorization', r.status_code, r.text)
        access_token = json.loads(r.text)['access_token']
        r = await requests.get(link, headers={'Authorization': 'Bearer ' + access_token})
        print('spotify data', r.status_code)
        j = json.loads(r.text)
        # TODO: handle multiple artists
        return (j['name'], j['artists'][0]['name'])
    except Exception as e:
        await ctx.send("failed to parse your spotify link :/")
        await ctx.send(f"{e}")


@bot.command()
async def song(ctx, *args):
    """
    just throw all the song related commands in here
    """
    if len(args) == 0:
        await song_help(ctx)
    elif args[0] == 'help':
        await song_help(ctx)
    elif len(args) == 1:
        try:
            song_id = int(args[0], 16)
        except ValueError:
            await ctx.send("invalid song id, please use: !song <song_id:hex>\n" + "for other usages of !song, please do !song help")
        else:
            await view_song(ctx, song_id)
    else:
        await ctx.send("unknown usage for !song. :/")
        await song_help(ctx)


async def song_help(ctx):
    await ctx.send("usage:")
    await ctx.send("I'm too lazy to write this, this is constatly changign anyway :p")


async def artist_string(conn, song_id):
    artists = await conn.fetch(f"SELECT id, name, english_name FROM artists WHERE id IN (SELECT unnest(artist_ids) FROM songs WHERE id = {song_id})")
    if len(artists) == 0:
        return "???"

    def artist_string_single(artist):
        s = f"{artist[1]} "
        if not artist[2] is None:
            s += f"({artist[2]}) "
        s += f"`{artist[0]:x}`"
        return s

    return ', '.join([artist_string_single(artist) for artist in artists])


async def view_song(ctx, song_id):
    conn = await asyncpg.connect(DATABASE_URL)
    message = await song_info_string(conn, song_id)
    if message is None:
        await ctx.send(f"cannot find song with id {song_id}")
    await ctx.send(message)


async def song_info_string(conn, song_id):
    song = await conn.fetchrow(f"SELECT name, english_name, rating, rating_num FROM songs WHERE id = {song_id}")
    if song is None:
        return
    message = f"{song[0]}"
    if not song[1] == '':
        message += f" ({song[1]})"
    message += "  by  "
    message += await artist_string(conn, song_id)
    message += "\n"
    if song[3] != 0:
        message += f"rating: {song[2]:.2f} / 10\n"
    message += f"song id: `{song_id:x}`\n"
    tags = await conn.fetch(f"SELECT names FROM tags WHERE id IN (SELECT unnest(tag_ids) FROM songs WHERE id = {song_id})")
    print(tags)
    if len(tags) > 0:
        message += f"tags: {', '.join([tag['names'][0] for tag in tags])}\n"
    links = await conn.fetch(f"SELECT type, link FROM links WHERE song_id = {song_id}")
    for link in links:
        message += f"{link[0]} link: {link[1]}\n"
    return message


@bot.command(aliases=['editsong'])
async def edit_song(ctx, *args):
    if len(args) < 3:
        await edit_song_help(ctx)
        return
    try:
        song_id = int(args[0], 16)
    except ValueError:
        await ctx.send("song id should be a hex number")
        # await edit_song_help(ctx)
        return
    # TODO: security!!
    conn = await asyncpg.connect(DATABASE_URL)
    if args[1] == 'name':
        await conn.execute(f"UPDATE songs SET name = '{args[2]}' WHERE id = {song_id}")
        await ctx.send("song name has been chagned")
    elif args[1] == 'english_name':
        await conn.execute(f"UPDATE songs SET english_name = '{args[2]}' WHERE id = {song_id}")
        await ctx.send("song english name has been chagned")
    elif args[1] == 'id':
        try:
            new_id = int(args[2], 16)
        except ValueError:
            await ctx.send("new song id should be a hex number")
            return
        matching_song = await conn.fetchval(f"SELECT name FROM songs WHERE id = {new_id}")
        if not matching_song is None:
            await ctx.send(f"there is another song entry with id {new_id:x}: {matching_song}")
            return
        await conn.execute(f"UPDATE songs SET id = {new_id} WHERE id = {song_id}")
        await conn.execute(f"UPDATE links SET song_id = {new_id} WHERE id = {song_id}")
        song_name = await conn.fetchval(f"SELECT name FROM songs WHERE id = {new_id}")
        await ctx.send(f"song id of {song_name} has been chagned")
    else:
        await edit_song_help(ctx)


@bot.command()
async def songs(ctx, page=1):
    try:
        page = int(page)
    except ValueError:
        await ctx.send("page should be an integer")
        return
    page -= 1
    if page < 0:
        await ctx.send("page number should be a positive integer")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    songs = await conn.fetch(f"SELECT * FROM songs ORDER BY time_added DESC LIMIT {ROWS_PER_PAGE} OFFSET {page * ROWS_PER_PAGE}")
    if len(songs) == 0:
        await ctx.send(f"There is no page {page + 1}")
        return
    display_text = ""
    for i, row in enumerate(songs):
        idx = i + 1 + page * ROWS_PER_PAGE
        display_text += f"{idx}. {row['name']} `{row['id']:x}`"
        display_text += "  by  "
        display_text += await artist_string(conn, row['id'])
        display_text += "\n"
    await ctx.send(display_text)


async def edit_song_help(ctx):
    help_text = "usage:\n"
    help_text += "!edit_song <song_id:hex> name <new_name:string>\n"
    help_text += "!edit_song <song_id:hex> english_name <new_english_name:string>\n"
    help_text += "!edit_song <song_id:hex> id <new_id:hex>\n"
    await ctx.send(help_text)

# =========================
# artist
# =========================


@bot.command()
async def artist(ctx, *args):
    """
    just throw all the artist related commands in here
    """
    if len(args) == 0:
        await artist_help(ctx)
    elif args[0] == 'help':
        await artist_help(ctx)
    elif args[0] == 'add':
        if len(args) != 2:
            await ctx.send("usage: !artist add <artist_name:string>")
            return
        await add_artist(ctx, args[1])
    elif len(args) == 1:
        try:
            artist_id = int(args[0], 16)
        except ValueError:
            await ctx.send("invalid artist id, please use: !artist <artist_id:hex>\n" + "for other usages of !artist, please do !artist help")
        else:
            await view_artist(ctx, artist_id)
    else:
        await ctx.send("unknown usage for !artist. :/")
        await artist_help(ctx)


async def view_artist(ctx, artist_id):
    conn = await asyncpg.connect(DATABASE_URL)
    artist = await conn.fetchrow(f"SELECT name, english_name FROM artists WHERE id = {artist_id}")
    if artist is None:
        await ctx.send(f"cannot find artist with id {artist_id:x}")
    else:
        artist_message = f"{artist[0]} "
        if not artist[1] is None:
            artist_message += f"({artist[1]}) "
        artist_message += f"`{artist_id:x}`"
        artist_message += "\n"
        songs = await conn.fetch(f"SELECT id, name FROM songs WHERE {artist_id} = ANY(artist_ids)")
        if len(songs) > 0:
            artist_message += f"songs ({len(songs)}):\n"
        for song in songs[:10]:
            artist_message += f"{song[1]} `{song[0]}`\n"
        await ctx.send(artist_message)


@bot.command()
async def edit_artist(ctx, *args):
    if len(args) < 3:
        await edit_artist_help(ctx)
        return
    try:
        artist_id = int(args[0], 16)
    except ValueError:
        ctx.send("arist id should be a hex number")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    # TODO: security!!
    if args[1] == 'name':
        await conn.execute(f"UPDATE artists SET name = '{args[2]}' WHERE id = {artist_id}")
        await ctx.send("artist name has been chagned")
    elif args[1] == 'english_name':
        await conn.execute(f"UPDATE artists SET english_name = '{args[2]}' WHERE id = {artist_id}")
        await ctx.send("artist english name has been chagned")
    elif args[1] == 'id':
        try:
            new_id = int(args[2], 16)
        except ValueError:
            await ctx.send("new artist id should be a hex number")
            return
        artist_name = await conn.fetchval(f"SELECT name FROM artist WHERE id = {new_id}")
        if not artist_name is None:
            await ctx.send(f"there is another artist entry with id {new_id:x}: {artist_name}")
            return
        await conn.execute(f"UPDATE artists SET id = {new_id} WHERE id = {artist_id}")
        await conn.execute(f"UPDATE songs SET artist_ids = array_replace(artist_ids, {artist_id}, {new_id})")
        artist_name = await conn.fetchval(f"SELECT name FROM artists WHERE id = {new_id}")
        await ctx.send(f"artist id of {artist_name} has been chagned")
    else:
        await edit_artist_help(ctx)


async def edit_artist_help(ctx):
    help_text = "usage:\n"
    help_text += "I'm too lazy"
    await ctx.send(help_text)


async def artist_help(ctx):
    help_text = "usage:\n"
    help_text += "I'm too lazy to do this atm"
    await ctx.send(help_text)


@bot.command(aliases=['addartist'])
async def add_artist(ctx, artist_name):
    conn = await asyncpg.connect(DATABASE_URL)
    existing = await conn.fetchval("SELECT id FROM artists WHERE name = ($1)", artist_name)
    if not existing is None:
        await ctx.send(f"There is already an database entry for {artist_name}: `{existing}`")
        return
    artist_id = await get_new_id(conn, 'artists')
    await conn.execute("INSERT INTO artists(id, name) VALUES (($1), ($2))", artist_id, artist_name)
    await ctx.send(f"created artist entry {artist_name} `{artist_id:x}`")

# =========================
# tags
# =========================


@bot.command()
async def tag(ctx, *args):
    if len(args) == 0:
        await tag_help(ctx)
    elif len(args) == 1:
        if args[0] == 'help':
            await tag_help(ctx)
        else:
            await view_tag(ctx, args[0])
    elif args[0] == 'song':
        if len(args[1:]) != 2:
            await ctx.send("usage: !tag song <song_id:hex> <tag_id:hex>")
            return
        await tag_song(ctx, args[1], args[2])
    elif len(args) == 2:
        await tag_song(ctx, args[0], args[1])


async def tag_help(ctx):
    help_text = "usage:\n"
    help_text += "!tag help\n"
    help_text += "!tag <tag_id:hex>\n"
    help_text += "!tag <name:string>\n"
    help_text += "!tag song <song_id:hex> <tag_id:hex>\n"
    await ctx.send(help_text + "too lazy to write down all other !tag help")


@bot.command(aliases=['viewtag'])
async def view_tag(ctx, tag_info):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        tag_id = int(tag_info, 16)
        tag_names = await conn.fetchval(f"SELECT names FROM tags WHERE id = {tag_id}")
    except ValueError:
        tag_id, tag_names = await conn.fetchrow(f"SELECT id, names FROM tags WHERE '{tag_info}' = ANY(tags.names)")
    display_text = f"{tag_names[0]} "
    if len(tag_names) > 1:
        display_text += f"({', '.join(tag_names[1:])}) "
    display_text += f"`{tag_id}`\n"
    songs = await conn.fetch(f"SELECT id, name FROM songs WHERE {tag_id} = ANY(songs.tag_ids)")
    if len(songs) > 0:
        display_text += f"songs with tag ({min(10, len(songs))} / {len(songs)}):\n"
        for song in songs[:10]:
            display_text += f"{song['name']} `{song['id']}`\n"
    await ctx.send(display_text)


@bot.command(aliases=['tagsong'])
async def tag_song(ctx, song_id, tag_info):
    try:
        song_id = int(song_id, 16)
    except ValueError:
        await ctx.send("song id should be a hex number")
    conn = await asyncpg.connect(DATABASE_URL)
    song_tags = await conn.fetchrow(
        f"SELECT tag_ids FROM songs WHERE id = {song_id}")
    if song is None:
        await ctx.send(f"cannot find song with id {song_id}")
        return

    try:
        tag_id = int(tag_info)
        tag_names = await conn.fetchval(f"SELECT names FROM tags WHERE id = {tag_id}")
        # TODO: repeated code
        if tag_names is None:
            await ctx.send(f"cannot find tag with id {tag_info}")
            return
    except ValueError:
        row = await conn.fetchrow(f"SELECT id, names FROM tags WHERE '{tag_info}' = ANY(names)")
        if row is None:
            await ctx.send(f"cannot find any tag with name {tag_info}")
            return
        tag_id, tag_names = row

    if tag_id in song_tags:
        await ctx.send(f"song {song_id} already has tag {tag_names[0]} ({tag_id})")
        return
    await conn.execute(f"UPDATE songs SET tag_ids = tag_ids || {tag_id} WHERE id = {song_id}")
    await ctx.send(f"song {song_id} has been tagged {tag_names[0]} `{tag_id}`")


@bot.command(aliases=['untagsong', 'untag_song'])
async def untag(ctx, *args):
    """
    remove a tag from a song
    usage: !untag <song_id:hex> <tag_id:hex>
    for other usages, I'm too lazy to document
    """
    if len(args) == 0:
        await untag_help(ctx)
        return
    if args[0] == 'song':
        await untag(ctx, args[1:])
        return
    if len(args) != 2:
        await untag_help(ctx)
        return
    await untag_song(ctx, args[0], args[1])


async def untag_help(ctx):
    await ctx.send()


async def untag_song(ctx, song_id, tag_info):
    try:
        song_id = int(song_id, 16)
    except ValueError:
        await ctx.send("song id should be a hex number")
    conn = await asyncpg.connect(DATABASE_URL)
    song_tags = await conn.fetchval(
        f"SELECT tag_ids FROM songs WHERE id = {song_id}")
    if song is None:
        await ctx.send(f"cannot find song with id {song_id}")
        return

    try:
        tag_id = int(tag_info)
        tag_names = await conn.fetchval(f"SELECT names FROM tags WHERE id = {tag_id}")
        # TODO: repeated code
        if tag_names is None:
            await ctx.send(f"cannot find tag with id {tag_info}")
            return
    except ValueError:
        tag_id, tag_names = await conn.fetchval(f"SELECT id, names FROM tags WHERE '{tag_info}' = ANY(names)")
        if tag_id is None:
            await ctx.send(f"cannot find any tag with name {tag_info}")
            return

    if not tag_id in song_tags:
        await ctx.send(f"song {song_id} does not have tag {tag_names[0]} ({tag_id})")
        return
    await conn.execute(f"UPDATE songs SET array_remove(tag_ids, {tag_id}) WHERE id = {song_id}")
    await ctx.send(f"tag {tag_names[0]} `{tag_id}` has been removed from song {song_id}")


@bot.command()
async def tags(ctx, page=1):
    """
    do something tag related
    """
    try:
        page = int(page)
    except ValueError:
        await ctx.send("page should be an integer")
        return
    page -= 1
    if page < 0:
        await ctx.send("page number should be a positive integer")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    songs = await conn.fetch(f"SELECT * FROM tags ORDER BY id LIMIT {ROWS_PER_PAGE} OFFSET {page * ROWS_PER_PAGE}")
    if len(songs) == 0:
        await ctx.send(f"There is no page {page + 1}")
        return
    display_text = ""
    for i, row in enumerate(songs):
        idx = i + 1 + page * ROWS_PER_PAGE
        display_text += f"{idx}. {row['names'][0]} `{row['id']:x}` "
        if len(row['names']) > 1:
            display_text += f"({', '.join(row['names'][1:])})"
        display_text += "\n"
    await ctx.send(display_text)

# =========================
# rate
# =========================


@bot.command()
async def rate(ctx, *args):
    if len(args) == 0:
        await ctx.send("blah")
    elif args[0] == 'help':
        await ctx.send("blah")
    elif args[0] == "view" or args[0] == 'check':
        if len(args) < 3:
            await ctx.send("usage: !rate view <song_id:hex> <user_name:string>")
            return
        if args[1] == 'song':
            await ctx.send("not implmented yet")
        elif args[1] == 'user':
            await ctx.send("not implmented yet")
        else:
            await view_rating(ctx, args[1], args[2])
    elif len(args) == 1:
        await rate_react(ctx, args[0])
    elif len(args) == 2:
        await rate_with_rating(ctx, args[0], args[1])


async def view_rating(ctx, song_id, username):
    try:
        song_id = int(song_id, 16)
    except:
        await ctx.send("usage: !rate view <song_id:hex> <user_name:string>")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    song_name = await conn.fetchval(f"SELECT name FROM songs WHERE id = {song_id}")
    if song_name is None:
        await ctx.send(f"There is no song with id {song_id:x}")
        return
    rating = await conn.fetchval(f"SELECT value FROM ratings WHERE username = {username} AND song_id = {song_id}")
    if rating is None:
        await ctx.send(f"{username} has not rated the song {song_name}")
    else:
        await ctx.send(f"{username} rated the song {song_name} a {rating} / 10")


async def rate_react(ctx, song_id):
    try:
        song_id = int(song_id, 16)
    except:
        await ctx.send("usage: !rate <song_id: hex>")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    song_name = await conn.fetchval(f"SELECT name FROM songs WHERE id = {song_id}")
    if song_name is None:
        await ctx.send(f"There is no song with id {song_id:x}")
        return
    username = await get_or_create_user(ctx, conn, ctx.message.author.id)
    old_rating = await conn.fetchval(f"SELECT value FROM ratings WHERE username = '{username}' AND song_id = {song_id}")

    prompt_text = f"{song_name} `{song_id:x}`  by  {await artist_string(conn, song_id)}\n"
    if not old_rating is None:
        prompt_text += f"you previously rated the song {old_rating} / 10\n"
    prompt_text += "to stop rating this song react with ❌"
    prompt_msg = await ctx.send(prompt_text)
    rating_emojis = ["0️⃣",
                     "1️⃣",
                     "2️⃣",
                     "3️⃣",
                     "4️⃣",
                     "5️⃣",
                     "6️⃣",
                     "7️⃣",
                     "8️⃣",
                     "9️⃣",
                     "🔟",
                     '❌']
    for emoji in rating_emojis:
        await prompt_msg.add_reaction(emoji)

    def check(reaction, user):
        return reaction.message.id == prompt_msg.id and user == ctx.message.author and str(reaction.emoji) in rating_emojis

    try:
        reaction, _user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except:
        await prompt_msg.delete()
        return
    if str(reaction.emoji) == '❌':
        await prompt_msg.delete()
        return
    rating = rating_emojis.index(str(reaction.emoji))
    if old_rating is None:
        await conn.execute(f"INSERT INTO ratings(username, song_id, value) VALUES ('{username}', {song_id}, {rating})")
        row = await conn.fetchrow(f"SELECT rating_num, rating_total FROM songs WHERE id = {song_id}")
        await conn.execute(f"UPDATE songs SET rating_num = {row[0] + 1}, rating_total = {row[1] + rating}, rating = {(row[1] + rating) / (row[0] + 1)} WHERE id = {song_id}")
        await ctx.send(f"You've rated {song_name} `{song_id:x}` a {rating}")
    else:
        await conn.execute(f"UPDATE ratings SET value = {rating} WHERE username = '{username}' AND song_id = {song_id}")
        row = await conn.fetchrow(f"SELECT rating_num, rating_total FROM songs WHERE id = {song_id}")
        await conn.execute(f"UPDATE songs SET rating_total = {row[1] + rating - old_rating}, rating = {(row[1] + rating - old_rating) / row[0]} WHERE id = {song_id}")
        await ctx.send(f"You've changed your rating of {song_name} `{song_id:x}` from {old_rating} to {rating}")
    await prompt_msg.delete()


async def rate_with_rating(ctx, song_id, rating):
    try:
        song_id = int(song_id, 16)
        rating = int(rating, 10)
    except:
        await ctx.send("usage: !rate <song_id:hex> <rating:integer>")
        return
    if rating < 0 or rating > 10:
        await ctx.send(f"rating should be an integer between 0 and 10 (inclusive), not {rating}")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    song_name = await conn.fetchval(f"SELECT name FROM songs WHERE id = {song_id}")
    if song_name is None:
        await ctx.send(f"There is no song with id {song_id:x}")
        return

    username = await get_or_create_user(ctx, conn, ctx.message.author.id)
    old_rating = await conn.fetchval(f"SELECT value FROM ratings WHERE username = '{username}' AND song_id = {song_id}")

    if old_rating is None:
        await conn.execute(f"INSERT INTO ratings(username, song_id, value) VALUES ('{username}', {song_id}, {rating})")
        row = await conn.fetchrow(f"SELECT rating_num, rating_total FROM songs WHERE id = {song_id}")
        await conn.execute(f"UPDATE songs SET rating_num = {row[0] + 1}, rating_total = {row[1] + rating}, rating = {(row[1] + rating) / (row[0] + 1)} WHERE id = {song_id}")
        await ctx.send(f"You've rated {song_name} `{song_id:x}` a {rating}")
    else:
        await conn.execute(f"UPDATE ratings SET value = {rating} WHERE username = '{username}' AND song_id = {song_id}")
        row = await conn.fetchrow(f"SELECT rating_num, rating_total FROM songs WHERE id = {song_id}")
        await conn.execute(f"UPDATE songs SET rating_total = {row[1] + rating - old_rating}, rating = {(row[1] + rating - old_rating) / row[0]} WHERE id = {song_id}")
        await ctx.send(f"You've changed your rating of {song_name} `{song_id:x}` from {old_rating} to {rating}")


@bot.command()
async def review(ctx, song_id):
    try:
        song_id = int(song_id, 16)
    except:
        await ctx.send("usage: !review <song_id: hex>")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    song_name = await conn.fetchval(f"SELECT name FROM songs WHERE id = {song_id}")
    if song_name is None:
        await ctx.send(f"There is no song with id {song_id:x}")
        return
    username = await get_or_create_user(ctx, conn, ctx.message.author.id)
    row = await conn.fetchrow(f"SELECT review FROM ratings WHERE username = '{username}' AND song_id = {song_id}")
    if row is None:
        await ctx.send(f"You have not rated the song {song_name} `{song_id:x}`. Please rate the song before submitting a review.")
        return
    old_review = row[0]
    if not (old_review == '' or old_review is None):
        msg = await ctx.send(f"You have an old review of this song. Do you want to write a new review?" + "delete old review and write a new one ✅, see old review instead 👀, cancel action and don't do anything ❌")
        await msg.add_reaction('✅')
        await msg.add_reaction('👀')
        await msg.add_reaction('❌')

        def check(reaction, user):
            return reaction.message.id == msg.id and user == ctx.message.author and str(reaction.emoji) in ['✅', '👀', '❌']

        try:
            reaction, _user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
        except:
            pass
        await msg.delete()
        if str(reaction.emoji) == '✅':
            await ctx.send(f"Please write a new review for {song_name} `{song_id:x}`")
            # TODO: cancel writing review at this stage?
            # await msg

            def check_info(m):
                return m.author == ctx.message.author and m.content[0] != '!'

            new_review = await bot.wait_for('message', check=check_info)
            await conn.execute(f"UPDATE ratings SET review = ($1) WHERE username = '{username}' AND song_id = {song_id}", new_review.content)
            await ctx.send("Thank you for your review")
        elif str(reaction.emoji) == '👀':
            await ctx.send(f"Here is your previous review of {song_name} `{song_id:x}`:")
            await ctx.send(old_review)
        else:
            pass
    else:
        await ctx.send(f"Please write a new review for {song_name} `{song_id:x}`")
        # TODO: cancel writing review at this stage?
        # await msg

        def check_info(m):
            return m.author == ctx.message.author and m.content[0] != '!'

        new_review = await bot.wait_for('message', check=check_info)
        await conn.execute(f"UPDATE ratings SET review = ($1) WHERE username = '{username}' AND song_id = {song_id}", new_review.content)
        await ctx.send("Thank you for your review")


@bot.command(aliases=['rec'])
async def recommend(ctx, song_id, discord_id):
    try:
        song_id = int(song_id, 16)
        discord_id = int(discord_id, 10)
    except:
        await ctx.send("usage: !recommend <song_id:hex> <discord_id:integer>")
        return
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow(f"SELECT name, english_name, rating, rating_num FROM songs WHERE id = {song_id}")
    if row is None:
        await ctx.send(f"Couldn't find song with id {song_id:x}")
        return
    sender_name = await get_or_create_user(ctx, conn, ctx.message.author.id)
    rec_message = f"{sender_name} has recommended you the song:\n"
    rec_message += await song_info_string(conn, song_id)

    sender_rating_row = await conn.fetchrow("SELECT value, review FROM ratings WHERE username = ($1) AND song_id = ($2)", sender_name, song_id)
    if not sender_rating_row is None:
        rec_message += f"{sender_name} has rated this song {sender_rating_row[0]} / 10 "
        if not sender_rating_row[1] is None:
            rec_message += "with the following review:\n"
            rec_message += f"```\n"
            rec_message += sender_rating_row[1]
            rec_message += f"```\n"

    await bot.get_user(discord_id).send(rec_message)
    print(sender_name, 'recommended', song_id, discord_id)

if __name__ == "__main__":
    bot.run(TOKEN)
