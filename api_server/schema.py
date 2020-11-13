import graphene
from graphene import Node, Connection, Field
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from models import db_session
from models import User as UserModel, UserDiscord as UserDiscordModel, Song as SongModel, SongName as SongNameModel, Artist as ArtistModel, ArtistName as ArtistNameModel, Link as LinkModel, Rating as RatingModel, Tag as TagModel, TagName as TagNameModel, song_tag_table
from graphene_sqlalchemy_filter import FilterableConnectionField, FilterSet

from sqlalchemy import or_

from urllib.parse import unquote


class SongFilter(FilterSet):
    class Meta:
        model = SongModel
        fields = {
            'song_id': ['eq', 'ne', 'in', 'not_in'],
        }

    has_tag_id = graphene.Int()
    has_tag_id_in = graphene.List(graphene.Int)
    by_artist_id = graphene.Int()
    by_artist_id_in = graphene.List(graphene.Int)
    name = graphene.String()
    name_in = graphene.List(graphene.String)

    @staticmethod
    def has_tag_id_filter(_info, _query, value):
        return SongModel.tags.any(TagModel.tag_id == value)

    @staticmethod
    def has_tag_id_in_filter(_info, _query, value):
        return SongModel.tags.any(TagModel.tag_id.in_(value))

    @staticmethod
    def by_artist_id_filter(_info, _query, value):
        return SongModel.artists.any(ArtistModel.artist_id == value)

    @staticmethod
    def by_artist_id_in_filter(_info, _query, value):
        return SongModel.artists.any(ArtistModel.artist_id.in_(value))

    # TODO: normalize name when matching?
    @staticmethod
    def name_filter(_info, _query, value):
        return or_(SongModel.name == value,
                   SongModel.alt_names.any(SongNameModel.name == value))

    @staticmethod
    def name_in_filter(_info, _query, value):
        return or_(SongModel.name.in_(value),
                   SongModel.alt_names.any(SongNameModel.name.in_(value)))


class TagFilter(FilterSet):
    class Meta:
        model = TagModel
        fields = {
            'tag_id': ['eq', 'ne', 'in', 'not_in']
        }

    name = graphene.String()
    name_in = graphene.List(graphene.String)

    # TODO: normalize name when matching?
    @staticmethod
    def name_filter(_info, _query, value):
        return or_(TagModel.name == value,
                   TagModel.alt_names.any(TagNameModel.name == value))

    @staticmethod
    def name_in_filter(_info, _query, value):
        return or_(TagModel.name.in_(value),
                   TagModel.alt_names.any(TagNameModel.name.in_(value)))


class ArtistFilter(FilterSet):
    class Meta:
        model = ArtistModel
        fields = {
            'artist_id': ['eq', 'ne', 'in', 'not_in']
        }

    name = graphene.String()
    name_in = graphene.List(graphene.String)

    # TODO: normalize name when matching?
    @staticmethod
    def name_filter(_info, _query, value):
        return or_(ArtistModel.name == value,
                   ArtistModel.alt_names.any(ArtistNameModel.name == value))

    @staticmethod
    def name_in_filter(_info, _query, value):
        return or_(ArtistModel.name.in_(value),
                   ArtistModel.alt_names.any(ArtistNameModel.name.in_(value)))


class LinkFilter(FilterSet):
    class Meta:
        model = LinkModel
        fields = {
            'link': ['eq', 'ne', 'in', 'not_in'], 'type': ['eq', 'ne', 'in', 'not_in']
        }


class CustomField(FilterableConnectionField):
    filters = {
        SongModel: SongFilter(),
        TagModel: TagFilter(),
        LinkModel: LinkFilter(),
        ArtistModel: ArtistFilter(),
    }


class User(SQLAlchemyObjectType):
    class Meta:
        model = UserModel
        interfaces = (Node, )
        exclude_fields = ('password',)
        connection_field_factory = CustomField.factory


class UserNodeConnection(Connection):
    class Meta:
        node = User


class UserDiscord(SQLAlchemyObjectType):
    class Meta:
        model = UserDiscordModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class UserDiscordNodeConnection(Connection):
    class Meta:
        node = UserDiscord


class Song(SQLAlchemyObjectType):
    class Meta:
        model = SongModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class SongNodeConnection(Connection):
    class Meta:
        node = Song


class SongName(SQLAlchemyObjectType):
    class Meta:
        model = SongNameModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class SongNameNodeConnection(Connection):
    class Meta:
        node = SongName


class Artist(SQLAlchemyObjectType):
    class Meta:
        model = ArtistModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class ArtistNodeConnection(Connection):
    class Meta:
        node = Artist


class ArtistName(SQLAlchemyObjectType):
    class Meta:
        model = ArtistNameModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class ArtistNameNodeConnection(Connection):
    class Meta:
        node = ArtistName


class Link(SQLAlchemyObjectType):
    class Meta:
        model = LinkModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class LinkNodeConnection(Connection):
    class Meta:
        node = Link


class Rating(SQLAlchemyObjectType):
    class Meta:
        model = RatingModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class RatingNodeConnection(Connection):
    class Meta:
        node = Rating


class Tag(SQLAlchemyObjectType):
    class Meta:
        model = TagModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class TagNodeConnection(Connection):
    class Meta:
        node = Tag


class TagName(SQLAlchemyObjectType):
    class Meta:
        model = TagNameModel
        interfaces = (Node, )
        connection_field_factory = CustomField.factory


class TagNameNodeConnection(Connection):
    class Meta:
        node = TagName


class Query(graphene.ObjectType):
    node = Node.Field()

    songs = CustomField(SongNodeConnection)
    artists = CustomField(ArtistNodeConnection)
    tags = CustomField(TagNodeConnection)
    links = CustomField(LinkNodeConnection)
    ratings = CustomField(RatingNodeConnection)

    login = Field(graphene.Boolean,
                  username=graphene.String(),
                  password=graphene.String())

    def resolve_login(self, info, username, password):
        user = UserModel.query.get(username)
        if user is None:
            return False
        if user.password == password:
            return True
        return False


class NewArtistMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    artist = graphene.Field(lambda: Artist)

    def mutate(self, info, name):
        new_artist = ArtistModel(name=name)
        db_session.add(new_artist)
        db_session.commit()
        return NewArtistMutation(artist=new_artist)


class QueryOrCreateArtistMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    artists = graphene.List(Artist)

    def mutate(self, info, name):
        matching = ArtistModel.query.filter(or_(
            ArtistModel.name == name, ArtistModel.alt_names.any(ArtistNameModel.name == name))).all()
        if len(matching) == 0:
            # create
            new_artist = ArtistModel(name=name)
            db_session.add(new_artist)
            db_session.commit()
            return QueryOrCreateArtistMutation(artists=[new_artist])
        else:
            # TODO: what to do when more than one match???
            return QueryOrCreateArtistMutation(artists=matching)


class RemoveArtistMutation(graphene.Mutation):
    class Arguments:
        artist_id = graphene.Int(required=True)

    artist_id = graphene.Int()

    def mutate(self, info, artist_id):
        artist = ArtistModel.query.get(artist_id)
        db_session.delete(artist)
        db_session.commit()
        return RemoveArtistMutation(artist_id=artist_id)


class NewSongMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        artist_ids = graphene.List(graphene.Int)
        new_artist_names = graphene.List(graphene.String)
        alt_names = graphene.List(graphene.String)

    song = graphene.Field(lambda: Song)

    def mutate(self, info, name, artist_ids=None, new_artist_names=None, alt_names=None):
        new_song = SongModel(name=name)
        if artist_ids:
            for artist_id in artist_ids:
                artist = ArtistModel.query.get(artist_id)
                new_song.artists.append(artist)
        if new_artist_names:
            for name in new_artist_names:
                artist = ArtistModel(name=name)
                db_session.add(artist)
                new_song.artists.append(artist)
        if alt_names:
            for name in alt_names:
                alt_name = SongNameModel(name=name)
                new_song.alt_names.append(alt_name)
        db_session.add(new_song)
        db_session.commit()
        return NewSongMutation(song=new_song)


class RemoveSongMutation(graphene.Mutation):
    class Arguments:
        song_id = graphene.Int(required=True)

    song_id = graphene.Int()

    def mutate(self, info, song_id):
        song = SongModel.query.get(song_id)
        db_session.delete(song)
        db_session.commit()
        return RemoveSongMutation(song_id=song_id)


class NewTagMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    tag_id = graphene.Int()

    def mutate(self, info, name):
        tag = TagModel(name=name)
        db_session.add(tag)
        db_session.commit()
        return NewTagMutation(tag_id=tag.tag_id)


class TagSongMutation(graphene.Mutation):
    class Arguments:
        song_id = graphene.Int(required=True)
        tag_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, song_id, tag_id):
        song = SongModel.query.get(song_id)
        tag = TagModel.query.get(tag_id)
        song.tags.append(tag)
        db_session.commit()
        return TagSongMutation(ok=True)


class UntagSongMutation(graphene.Mutation):
    class Arguments:
        song_id = graphene.Int(required=True)
        tag_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, song_id, tag_id):
        song = SongModel.query.get(song_id)
        tag = TagModel.query.get(tag_id)
        song.tags.remove(tag)
        db_session.commit()
        return UntagSongMutation(ok=True)


class SongChangeNameMutation(graphene.Mutation):
    class Arguments:
        song_id = graphene.Int(required=True)
        new_name = graphene.String(required=True)

    old_name = graphene.String()

    def mutate(self, info, song_id, new_name):
        song = SongModel.query.get(song_id)
        old_name = song.name
        song.name = new_name
        db_session.commit()
        return SongChangeNameMutation(old_name=old_name)


class SongAddNameMutation(graphene.Mutation):
    class Arguments:
        song_id = graphene.Int(required=True)
        name = graphene.String(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, song_id, name):
        song = SongModel.query.get(song_id)
        song.alt_names.append(SongNameModel(name=name))
        db_session.commit()
        return SongAddNameMutation(ok=True)


class SongRemoveNameMutation(graphene.Mutation):
    class Arguments:
        name_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, name_id):
        song_name = SongNameModel.query.get(name_id)
        db_session.delete(song_name)
        db_session.commit()
        return SongAddNameMutation(ok=True)


class ArtistChangeNameMutation(graphene.Mutation):
    class Arguments:
        artist_id = graphene.Int(required=True)
        new_name = graphene.String(required=True)

    old_name = graphene.String()

    def mutate(self, info, artist_id, new_name):
        song = ArtistModel.query.get(artist_id)
        old_name = song.name
        song.name = new_name
        db_session.commit()
        return ArtistChangeNameMutation(old_name=old_name)


class ArtistAddNameMutation(graphene.Mutation):
    class Arguments:
        artist_id = graphene.Int(required=True)
        name = graphene.String(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, artist_id, name):
        artist = ArtistModel.query.get(artist_id)
        artist.alt_names.append(ArtistNameModel(name=name))
        db_session.commit()
        return ArtistAddNameMutation(ok=True)


class ArtistRemoveNameMutation(graphene.Mutation):
    class Arguments:
        name_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, name_id):
        artist_name = ArtistNameModel.query.get(name_id)
        db_session.delete(artist_name)
        db_session.commit()
        return ArtistAddNameMutation(ok=True)


class NewLinkMutation(graphene.Mutation):
    class Arguments:
        link = graphene.String(required=True)
        link_type = graphene.String(required=True)
        song_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, link, link_type, song_id):
        song = SongModel.query.get(song_id)
        new_link = LinkModel(link=link, link_type=link_type, song=song)
        db_session.add(new_link)
        db_session.commit()
        return NewLinkMutation(ok=True)


class RemoveLinkMutation(graphene.Mutation):
    class Arguments:
        link = graphene.String(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, link):
        link_obj = LinkModel.query.get(link)
        db_session.delete(link_obj)
        db_session.commit()
        return RemoveLinkMutation(ok=True)


class MergeSongMutation(graphene.Mutation):
    class Arguments:
        merge_to_id = graphene.Int(required=True)
        duplicate_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, merge_to_id, duplicate_id):
        if merge_to_id == duplicate_id:
            return MergeSongMutation(ok=False)
        merge_to_song = SongModel.query.get(merge_to_id)
        duplicate_song = SongModel.query.get(duplicate_id)

        merge_to_song.alt_names.append(SongNameModel(name=duplicate_song.name))
        # TODO: if duplicate song has an identical alt name, the merged song will have 2 alt names that are identical, we need to filter alt names first
        for alt_name in duplicate_song.alt_names:
            alt_name.song = merge_to_song
        for artist in duplicate_song.artists:
            merge_to_song.artists.append(artist)
        for tag in duplicate_song.tags:
            merge_to_song.tags.append(tag)
        for link in duplicate_song.links:
            link.song = merge_to_song

        db_session.delete(duplicate_song)
        db_session.commit()
        return MergeSongMutation(ok=True)


class MergeArtistMutation(graphene.Mutation):
    class Arguments:
        merge_to_id = graphene.Int(required=True)
        duplicate_id = graphene.Int(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, merge_to_id, duplicate_id):
        if merge_to_id == duplicate_id:
            return MergeSongMutation(ok=False)
        merge_to_artist = ArtistModel.query.get(merge_to_id)
        duplicate_artist = ArtistModel.query.get(duplicate_id)

        merge_to_artist.alt_names.append(
            ArtistNameModel(name=duplicate_artist.name))
        for alt_name in duplicate_artist.alt_names:
            alt_name.artist = merge_to_artist
        for song in duplicate_artist.songs:
            song.artists.append(merge_to_artist)

        db_session.delete(duplicate_artist)
        db_session.commit()
        return MergeArtistMutation(ok=True)


class CreateUserMutation(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, username, password):
        matching_user = UserModel.query.get(username)
        if not matching_user is None:
            return CreateUserMutation(ok=False)
        new_user = UserModel(username=username, password=password)
        db_session.add(new_user)
        db_session.commit()
        return CreateUserMutation(ok=True)


class ReviewMutation(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        song_id = graphene.Int(required=True)
        value = graphene.Float(required=True)
        detail_review = graphene.String()

    ok = graphene.Boolean()
    review_id = graphene.Int()

    def mutate(self, info, username, password, song_id, value, detail_review=None):
        matching_user = UserModel.query.get(username)
        if matching_user is None:
            return ReviewMutation(ok=False, review_id=0)
        if matching_user.password != password:
            return ReviewMutation(ok=False, review_id=0)
        song = SongModel.query.get(song_id)
        reviews = RatingModel.query.filter(
            RatingModel.user == matching_user).filter(RatingModel.song == song)
        if reviews.count() == 0:
            if detail_review:
                new_review = RatingModel(
                    user=matching_user, song=song, value=value, review=unquote(detail_review))
            else:
                new_review = RatingModel(
                    user=matching_user, song=song, value=value)
            db_session.add(new_review)
            db_session.commit()
            return ReviewMutation(ok=True, review_id=new_review.rating_id)
        else:
            # There should only be one
            review = reviews.one()
            review.value = value
            if review:
                review.review = unquote(detail_review)
            db_session.commit()
            return ReviewMutation(ok=True, review_id=review.rating_id)


class Mutation(graphene.ObjectType):
    new_artist = NewArtistMutation.Field()
    query_or_create_artist = QueryOrCreateArtistMutation.Field()
    remove_artist = RemoveArtistMutation.Field()
    new_song = NewSongMutation.Field()
    remove_song = RemoveSongMutation.Field()
    new_tag = NewTagMutation.Field()
    tag_song = TagSongMutation.Field()
    untag_song = UntagSongMutation.Field()

    song_change_name = SongChangeNameMutation.Field()
    song_add_name = SongAddNameMutation.Field()
    song_remove_name = SongRemoveNameMutation.Field()
    artist_change_name = ArtistChangeNameMutation.Field()
    artist_add_name = ArtistAddNameMutation.Field()
    artist_remove_name = ArtistRemoveNameMutation.Field()

    new_link = NewLinkMutation.Field()
    remove_link = RemoveLinkMutation.Field()

    merge_song = MergeSongMutation.Field()
    merge_artist = MergeArtistMutation.Field()

    create_user = CreateUserMutation.Field()

    review = ReviewMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
