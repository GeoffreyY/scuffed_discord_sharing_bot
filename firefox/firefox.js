console.log('testing script');

browser.runtime.onMessage.addListener(
    function (msg, sender, sendResponse) {
        console.log('onMessage', msg);
        if (msg.tab_type == "youtube") {
            data = parse_youtube();
            console.log('returning youtube page data', data);
            sendResponse(data);
        } else if (msg.tab_type == "spotify") {
            data = parse_spotify();
            console.log('returning spotify page data', data);
            sendResponse(data);
        } else {
            console.log('what')
            sendResponse({ song_name: 'nah' });
        }
    }
);

function parse_youtube() {
    //console.log('jquery version', $().jquery);
    // it doesn't update
    // FUCK

    /*song = $('meta[itemprop="name"]')[0].attributes['content'].nodeValue;
    artist = $('link[itemprop="name"]')[0].attributes['content'].nodeValue;
    console.log($('link[itemprop="name"]'));*/
    //console.log(song, artist);
    /*song = $('meta[itemprop="name"]')[0].attributes['content'].nodeValue;
    artist = $('link[itemprop="name"]')[0].attributes['content'].nodeValue;
    console.log($('title')[0]);
    console.log(document.documentElement.innerHTML.split("Subscribe to "));
    console.log(document.documentElement.innerHTML.split("Subscribe to ")[1].split('"')[0]);*/

    // FUCK YOU YOUTUBE
    /*song = $('title')[0].innerHTML;
    song = song.split(' - YouTube')[0];
    //console.log($('script[type="application/ld+json"]').last()[0]);
    arr = document.documentElement.innerHTML.split("\"subscribeAccessibility\":{\"accessibilityData\":{\"label\":\"Subscribe to ");
    artist = arr[1].split('"')[0];
    console.log(typeof artist, artist)
    if (artist == 'channel') {
        artist = arr[arr.length - 3].split('"')[0];
    }
    if (artist.includes(' subscribers')) {
        artist = artist.split(' subscribers')[0].split('. ');
        artist.pop();
        artist = artist.join('. ');
    } else {
        artist = artist.substring(0, artist.length - 1);
    }*/

    // FUCK
    j = JSON.parse($('script[type="application/ld+json"]').last()[0].innerHTML);
    //console.log(j);
    song = j['name'];
    artist = j['author'];
    //console.log(song);
    //console.log(artist);
    data = { song_name: song, artist_name: artist };
    return data
}

function parse_spotify() {
    now_playing = $('.now-playing').children('div:nth-child(2)');
    //console.log($('.now-playing').html());
    console.log('testing', $('.now-playing').children('div:nth-child(2)').html());
    song_name = now_playing.children('div:nth-child(1)').children('span').children('a').text();
    artist_name = now_playing.children('div:nth-child(2)').children('span').children('span').children('a').text();
    song_name = song_name.substring(0, song_name.length / 2);
    artist_name = artist_name.substring(0, artist_name.length / 2);
    return { song_name: song_name, artist_name: artist_name }
}