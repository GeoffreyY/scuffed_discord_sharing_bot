server_url = 'http://127.0.0.1:5000/graphql'

async function query_graphql(payload, method = 'GET') {
    payload = "?query=" + encodeURIComponent(payload);
    return fetch(server_url + payload, { method: method }).then(response => response.json()).then(data => { if ('errors' in data) { for (error of data.errors) console.log(error.message) } return data }).then(data => data['data'])
}

site_type = "";

async function parse(tab) {
    domain = new URL(tab.url).hostname;
    if (domain == "www.youtube.com") {
        // check if link already exists in database
        payload = "{links(filters:{link:" + JSON.stringify(tab.url) + "}) { edges{ node{ song{ songId name artists{ edges{ node{ name } } } } } } }}";
        console.log(payload);
        existing = await query_graphql(payload);

        console.log('existing', existing, existing.links.edges.length);

        if (existing.links.edges.length > 0) {
            console.log('found');
            $('#site_type').text("Note: this link already exitsts in the database");
            song = existing.links.edges[0].node.song;
            song_name = song.name;
            artists = song.artists.edges.map((o) => o.node.name);
            $('#song_name').text(song_name);
            $('#artist_name_inner0').text(artists.shift());
            for (artist_name of artists) {
                add_artist_field();
                $('#artist_name_inner' + (artist_field_num - 1)).text(artist_name);
            }
            $('#link').text(tab.url);
            $('#goto_review').show();
            document.getElementById("goto_review").addEventListener("click", (() => rate(song.songId)));
        } else {
            parse_youtube(tab);
            site_type = "youtube"
        }
    } else if (domain == "open.spotify.com") {
        // we can't detect the link for spotify :/
        await parse_spotify(tab);
        site_type = "spotify"
    }
}

function parse_youtube(tab) {
    console.log('parsing youtube tab...', tab.id);
    console.log(tab.url, tab.title);
    chrome.tabs.sendMessage(tab.id, { tab_type: "youtube" }, function (msg) {
        console.log('onResponse', msg.song_name);
        $('#site_type').html("I have automatically extracted<br>the following from youtube:");
        $('#song_name').text(msg.song_name);
        $('#artist_name_inner0').text(msg.artist_name);
        $('#link').text(tab.url);
    });
}

async function parse_spotify(tab) {
    console.log('parsing spotify tab...', tab.id);
    console.log(tab.url, tab.title);

    chrome.tabs.sendMessage(tab.id, { tab_type: "spotify" }, function (msg) {
        console.log('onResponse', msg.song_name);
        $('#site_type').html(`I can't get spotify track links :(
        <br>Please manually enter the spotify track link
        <br>right click song -> Share -> Copy Song Link`);
        $('#song_name').text(msg.song_name);
        $('#artist_name_inner0').text(msg.artist_name);
        $('#link').text("<Please manually enter>");
    });
}

async function register() {
    username = $('#username').text();
    password = $('#password').text();
    if (username.length == 0) {
        $('#status').text("error: username should not be blank");
        return;
    }
    if (password.length == 0) {
        $('#status').text("error: password should not be blank");
        return;
    }
    register_payload = "mutation{createUser(username:\"" + username + "\", password:\"" + password + "\")}";
    res = await query_graphql(register_payload, 'POST');
    if (!res.login) {
        $("#status").text("Error: couldn't register. Username already used?");
        return;
    }
    await browser.storage.local.set({ "jp_music_bot_thing_account": { username: username, password: password } });
    $('#create_account').remove();
    $('#song_name_wrapper').show();
    $('#artist_name_wrapper').show();
    $('#link_wrapper').show();
    $('#submit').show();
    $("#status").text("Registered and logged in as " + username);
    browser.tabs.query({ active: true, currentWindow: true }, function (tabArray) {
        console.log(tabArray[0].url);
        (async () => await parse(tabArray[0]))();
    });
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("register").addEventListener("click", register);
});


async function login() {
    username = $('#username').text();
    password = $('#password').text();
    if (username.length == 0) {
        $('#status').text("Error: username should not be blank");
        return;
    }
    if (password.length == 0) {
        $('#status').text("Error: password should not be blank");
        return;
    }
    login_payload = "{login(username:\"" + username + "\", password:\"" + password + "\")}";
    res = await query_graphql(login_payload);
    if (!res.login) {
        $("#status").text("Error: couldn't login. Wrong password?");
        return;
    }
    await browser.storage.local.set({ "jp_music_bot_thing_account": { username: username, password: password } });
    $('#create_account').remove();
    $('#song_name_wrapper').show();
    $('#artist_name_wrapper').show();
    $('#link_wrapper').show();
    $('#submit').show();
    $("#status").text("Logged in as " + username);
    browser.tabs.query({ active: true, currentWindow: true }, function (tabArray) {
        console.log(tabArray[0].url);
        (async () => await parse(tabArray[0]))();
    });
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("login").addEventListener("click", login);
});


async function main() {
    let account = await browser.storage.local.get("jp_music_bot_thing_account");
    console.log(account);
    if (Object.keys(account).length == 0) {
        console.log("nothing!");
        $('#site_type').text("Please login first");
        $('#song_name_wrapper').hide();
        $('#artist_name_wrapper').hide();
        $('#link_wrapper').hide();
        $('#submit').hide();
    } else {
        $('#status').text('Welcome back ' + account.jp_music_bot_thing_account.username);
        $('#create_account').remove();
        console.log("something!");
        browser.tabs.query({ active: true, currentWindow: true }, function (tabArray) {
            console.log(tabArray[0].url);
            (async () => await parse(tabArray[0]))();
        });
    }
}

document.addEventListener('DOMContentLoaded', main);

async function submit_check() {
    console.log('checking for existing data before submitting...');
    $('#status').text("loading...");

    // check if we have matching link
    link = $('#link').text();
    link_payload = "{links(filters:{link:\"" + encodeURIComponent(link) + "\"}){edges{node{songId}}}}"
    link_res = await query_graphql(link_payload);
    if (link_res.links.edges.length > 0) {
        song_id = link_res.links.edges[0].node.songId
        $('#site_type').html(`this link is already in the database
        <br>song id: ${song_id}
        <br>do you want to update the information on this link instead?`);
        $('#submit').hide();
        $('#update_link_info').show();
        document.getElementById("update_link_info").addEventListener("click", update_link(song_id));
        return
    }

    // search for song name, and guess if song entry already exists
    song_name = $('#song_name').text();
    song_payload = "{songs(filters:{name:\"" + encodeURIComponent(song_name) + "\"}){edges{node{songId}}}}";
    song_res = await query_graphql(song_payload);

    if (song_res.songs.edges.length > 0) {
        $('#site_type').text("Song entry may already exist: song id " + song_res.songs.edges.map((x) => x.node.songId).join(', '));
        $('#submit').hide();
        $('#submit_confirm').show();
        if (song_res.songs.edges.length == 1) {
            $('#submit_new_link').show();
            document.getElementById("submit_new_link").addEventListener("click", submit_new_link(song_res.songs.edges[0].node.songId));
        } else {
            // TODO: what to do when there's more than one matching song?
        }
        return
    }

    await submit()
}

async function submit() {
    // can't be bothered to ask the user to check each artist
    // just create the artists if doesn't exist
    // merge the artist later if repeated
    artist_payload = "mutation{"
    i = 0
    artist_names = [];
    $('[id^=artist_name_inner]').each(function () { artist_names.push($(this).text()) });
    for (artist_name of artist_names) {
        console.log(artist_name);
        artist_payload += "artist_query_" + i + ":queryOrCreateArtist(name:\"" + encodeURIComponent(artist_name) + "\"){artists{artistId}}\n"
        i += 1;
    }
    artist_payload += "}";
    artist_res = await query_graphql(artist_payload, 'POST');
    artist_ids = [];
    for (k in artist_res) {
        artist_ids.push(artist_res[k].artists[0].artistId)
    }
    console.log(artist_ids);
    // now create the actual song
    song_payload = "mutation{newSong(name:\"" + encodeURIComponent(song_name) + "\",artistIds:[" + artist_ids.toString() + "]){song{songId}}}"
    song_res = await query_graphql(song_payload, 'POST');
    song_id = song_res.newSong.song.songId;
    $('#site_type').text("Created new song entry: song id " + song_id);

    if (site_type != "") {
        link = $('#link').text()
        add_link_payload = "mutation{newLink(link:\"" + encodeURIComponent(link) + "\",linkType:\"" + site_type + "\",songId:" + song_id + "){ok}}";
        add_link_ok = await query_graphql(add_link_payload, 'POST');
        $('#status').append("<br>Submitted new " + site_type + " link!");
    }

    $('#status').append("<br>Submitted!");

    await rate(song_id)
}

async function rate(song_id) {
    $('#song_name_wrapper').remove();
    $('#artist_name_wrapper').remove();
    $('#link_wrapper').remove();
    $('#submit').remove();
    $('#goto_review').remove();
    $('#review_wrapper').show();
    document.getElementById("submit_review").addEventListener("click", get_submit_review(song_id));
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("submit").addEventListener("click", submit_check);
});

artist_field_num = 1;

function add_artist_field() {
    console.log("adding artist", artist_field_num);
    // don't write over the div that has the add button
    new_div = document.createElement('div');
    new_div.innerHTML = "<div id=\"artist_name_inner" + artist_field_num + "\" contenteditable=\"true\" style=\"display: inline-block; color: #dddddd\">New artist " + artist_field_num + "</div><span id=\"remove_artist" + artist_field_num + "\"class=\"remove-button-div\">&nbsp;-&nbsp;</span>";
    new_div.setAttribute('id', 'artist_name_wrapper_inner' + artist_field_num);

    document.getElementById('artist_name_wrapper').appendChild(new_div);

    document.getElementById("remove_artist" + artist_field_num).addEventListener("click", remove_artist_field(artist_field_num));
    artist_field_num += 1;
    console.log(document.getElementById("artist_name_wrapper").innerHTML)
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("add_artist").addEventListener("click", add_artist_field);
});

function remove_artist_field(i) {
    let j = i;
    console.log('register', j);
    return () => {
        console.log('removing', j);
        document.getElementById("artist_name_wrapper_inner" + j).remove();
        console.log(artist_field_num);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("remove_artist0").addEventListener("click", remove_artist_field(0));
});

rating = 5;

function rating_click_func(star) {
    return () => {
        console.log('rating change from', rating, 'to', star);
        rating = star;
        for (j = 1; j <= 10; j++) {
            if (j <= rating) {
                $('#star' + j).text('★')
            } else {
                $('#star' + j).text('☆')
            }
        }
    }
}
for (star = 1; star <= 10; star++) {
    let s = star;
    document.addEventListener('DOMContentLoaded', function () {
        document.getElementById("star" + s).addEventListener("click", rating_click_func(s));
    });
}

function get_submit_review(song_id) {
    return async () => {
        console.log('rating of', rating);
        detail_review = $('#detailed_review').text();
        user_account = await browser.storage.local.get('jp_music_bot_thing_account');
        user_account = user_account.jp_music_bot_thing_account;
        if (detail_review == 'detailed_review_here' || detail_review == '') {
            // no detail review
            review_payload = `mutation{review(username: "${user_account.username}", password: "${user_account.password}", songId: ${song_id}, value: ${rating}){ok reviewId}}`;
            res = await query_graphql(review_payload, 'POST');
        } else {
            review_payload = `mutation{review(username: "${user_account.username}", password: "${user_account.password}", songId: ${song_id}, value: ${rating}, detailReview: "${encodeURIComponent(detail_review)}"){ok reviewId}}`;
            res = await query_graphql(review_payload, 'POST');
        }
        console.log(res);
        if (res.review.ok) {
            $('#status').append('<br>Review has been submitted: review id ' + res.review.reviewId)
        } else {
            $('#status').append("<br>Couldn't submit review for whatever reason")
        }
    }
}

// idk why I need to do this
document.addEventListener('DOMContentLoaded', function () {
    $("#submit_new_link").hide();
    $("#submit_confirm").hide();
    $("#update_link_info").hide();
    $("#goto_review").hide();
});

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("submit_confirm").addEventListener("click", submit);
});

function submit_new_link(song_id) {
    return async () => {
        link = $('#link').text()
        add_link_payload = "mutation{newLink(link:\"" + encodeURIComponent(link) + "\",linkType:\"" + site_type + "\",songId:" + song_id + "){ok}}";
        add_link_ok = await query_graphql(add_link_payload, 'POST');
        $('#status').append("<br>Submitted new " + site_type + " link!");

        $('#song_name_wrapper').remove();
        $('#artist_name_wrapper').remove();
        $('#link_wrapper').remove();
        $('#submit').remove();

        await rate(song_id)
    }
}

function update_link(song_id) {
    return async () => {
        $('#site_type').append("<br>Updating existing song isn't implemented yet");
    }
}