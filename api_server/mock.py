from models import db_session, User, Song, SongName, Artist, ArtistName, Link, Rating, Tag, TagName


def init_db():
    me = User(username='GeoffreyY',
              password='password123',
              discord_id=136047106757492736,
              is_admin=True)
    db_session.add(me)

    jpop = Tag(name='jpop')
    jpop.alt_names.append(TagName(name='j-pop'))

    _36kmps = Artist(name='時速36km')
    subarashi = Song(name='素晴らしい日々')
    subarashi.artists.append(_36kmps)
    subarashi_link = Link(
        link='https://www.youtube.com/watch?v=zcZRNWuI9pw', link_type='youtube', song=subarashi)
    subarashi_review = Rating(user=me, song=subarashi, value=10.0)
    subarashi.tags.append(jpop)
    db_session.add(subarashi)

    jazz = Tag(name='jazz')

    co_shu_nie = Artist(name='Cö shu Nie')
    co_shu_nie.alt_names.append(ArtistName(name='Co shu nie'))
    aquarium_fool = Song(name='水槽のフール')
    aquarium_fool.artists.append(co_shu_nie)
    aquarium_fool.alt_names.append(SongName(name='Fool in Tank'))
    aquarium_fool_link = Link(
        link="https://www.youtube.com/watch?v=PRtySh3ZZnU", link_type='youtube', song=aquarium_fool)
    aquarium_fool_link_spotify = Link(
        link='https://open.spotify.com/track/5TuiRpR8l9pdFSshvjPpla?si=0uBvPw29TtCCmmjT0Z42Ag', link_type='spotify', song=aquarium_fool)
    aquarium_fool_review = Rating(user=me, song=aquarium_fool, value=10.0,
                                  review="Another great song by Cö shu Nie, love the stacked vocals.")
    aquarium_fool.tags.append(jpop)
    aquarium_fool.tags.append(jazz)
    db_session.add(aquarium_fool)

    lisa = Artist(name='LiSA')
    uru = Artist(name='Uru')
    ayase = Artist(name='Ayase')
    reunion = Song(name='再会')
    reunion.artists.append(lisa)
    reunion.artists.append(uru)
    reunion.artists.append(ayase)
    reunion.alt_names.append(SongName(name='saikai'))
    reunion_link = Link(
        link='https://www.youtube.com/watch?v=impSuIygMiQ', link_type='youtube', song=reunion)
    reunion_review = Rating(user=me, song=reunion, value=9.0,)
    reunion.tags.append(jpop)
    db_session.add(reunion)

    racing_to_the_night = Song(name='夜に駆ける')
    racing_to_the_night.artists.append(ayase)
    racing_to_the_night.alt_names.append(SongName(name='racing to the night'))
    racing_to_the_night_link = Link(
        link='https://www.youtube.com/watch?v=x8VYWazR5mE', link_type='youtube', song=racing_to_the_night)
    db_session.add(racing_to_the_night)

    lone_digger = Song(name="Lone Digger")
    lone_digger.tags.append(jazz)
    db_session.add(lone_digger)

    db_session.commit()


def try_init_db():
    if db_session.query(Song.song_id).count() == 0:
        init_db()
