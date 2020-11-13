import datetime
from sqlalchemy import create_engine, Table, Column, Boolean, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref
#from sqlalchemy.orm import registry
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid


#engine = create_engine("sqlite:///database.sqlite3", echo=True, future=True)
engine = create_engine("sqlite:///database.sqlite3", echo=True, )
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
#mapper_registry = registry()
#Base = mapper_registry.generate_base()
Base = declarative_base()
Base.query = db_session.query_property()


class User(Base):
    __tablename__ = 'users'

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    discord_id = Column(Integer)
    is_admin = Column(Boolean, nullable=False, default=False)


# NOTE: field 'id' is used by graphene, so we can't have field named 'id'
class Song(Base):
    __tablename__ = 'songs'

    song_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    artists = relationship(
        'Artist', secondary='song_artist_table', backref='songs')
    tags = relationship('Tag', secondary='song_tag_table', backref='songs')
    time_created = Column(DateTime, server_default=func.now())
    time_updated = Column(DateTime, onupdate=func.now())


class SongName(Base):
    __tablename__ = 'song_names'

    song_name_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    song_id = Column(Integer, ForeignKey('songs.song_id'))
    song = relationship('Song', backref='alt_names')


class Artist(Base):
    __tablename__ = 'artists'

    artist_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    time_created = Column(DateTime, server_default=func.now())
    time_updated = Column(DateTime, onupdate=func.now())


class ArtistName(Base):
    __tablename__ = 'artist_names'

    artist_name_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    artist_id = Column(Integer, ForeignKey('artists.artist_id'))
    artist = relationship('Artist', backref='alt_names')


song_artist_table = Table('song_artist_table', Base.metadata,
                          Column('song_id', Integer,
                                 ForeignKey('songs.song_id')),
                          Column('artist_id', Integer,
                                 ForeignKey('artists.artist_id'))
                          )


class Tag(Base):
    __tablename__ = 'tags'

    tag_id = Column(Integer, primary_key=True)
    name = Column(String)


class TagName(Base):
    __tablename__ = 'tag_names'

    tag_name_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    tag_id = Column(Integer, ForeignKey(Tag.tag_id))
    tag = relationship('Tag', backref='alt_names')


song_tag_table = Table('song_tag_table', Base.metadata,
                       Column('song_id', Integer,
                              ForeignKey('songs.song_id')),
                       Column('tag_id', Integer,
                              ForeignKey('tags.tag_id'))
                       )


class Link(Base):
    __tablename__ = 'links'

    link = Column(String, primary_key=True)
    link_type = Column(String)
    song_id = Column(Integer, ForeignKey('songs.song_id'), nullable=False)
    song = relationship('Song', backref='links')


class Rating(Base):
    __tablename__ = 'ratings'

    rating_id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.username'), nullable=False)
    user = relationship('User', backref='ratings')
    song_id = Column(Integer, ForeignKey('songs.song_id'), nullable=False)
    song = relationship('Song', backref='ratings')
    value = Column(Float, nullable=False)
    review = Column(String)
    time_created = Column(DateTime, server_default=func.now())
    time_updated = Column(DateTime, onupdate=func.now())

    UniqueConstraint('user_id', 'song_id')


# mapper_registry.metadata.create_all(engine)
Base.metadata.create_all(engine)
