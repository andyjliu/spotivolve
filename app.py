import requests
from flask import Flask, request, redirect, g, render_template
from urllib.parse import quote
import json

app = Flask(__name__)

cid = 'ebd8cac9845048d99aca6a20739b8f89'
secret = 'c27e28a69a0d4f4c8682e99d248122c7'
redirect_uri = "https://safe-river-55295.herokuapp.com/callback/q"
scope = 'playlist-read-private user-top-read'

auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "scope": scope,
    # "state": STATE,
    # "show_dialog": SHOW_DIALOG_str,
    "client_id": cid
}

@app.route("/")
def index():
    #Authorization
    url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in auth_query_parameters.items()])
    auth_url = "{}/?{}".format("https://accounts.spotify.com/authorize", url_args)
    return(redirect(auth_url))

@app.route("/callback/q")
def callback():
    #Redirect upon authorization
    songid_dict = {}
    artists_dict = {}
    genres_dict = {}
    #get access token info from code
    code = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(code),
        "redirect_uri": redirect_uri,
        'client_id': cid,
        'client_secret': secret,
    }

    post_request = requests.post("https://accounts.spotify.com/api/token", data=code_payload)
    response_data = json.loads(post_request.text)

    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]
    token_type = response_data["token_type"]
    expires_in = response_data["expires_in"]

    authorization_header = {"Authorization": "Bearer {}".format(access_token)}

    #searches for Spotify-made 'your top songs' playlists
    search_url = "https://api.spotify.com/v1/search?q=%22Your%20Top%20Songs%22&type=playlist"
    search = json.loads((requests.get(search_url, headers=authorization_header).text))
    playlists = search["playlists"]["items"]
    playlist_ids = []

    #filter out playlists not made by official spotify account
    for i in range(0,len(playlists)):
        if playlists[i]["owner"]["external_urls"]["spotify"] == "https://open.spotify.com/user/spotify":
            playlist_ids.append(playlists[i]["uri"])

    #loop over all Your Top Songs playlists
    for playlist_id in playlist_ids:

        track_ids = []
        artist_ids = []
        genre_counts = {}
        artist_counts = {}

        #get year playlist corresponds to, as well as list of tracks it contains
        playlist_id = playlist_id.split(":")[-1]
        playlist = json.loads(requests.get("https://api.spotify.com/v1/playlists/" + playlist_id, headers=authorization_header).text) 
        year = playlist["name"].split(" ")[-1]
        tracks = json.loads(requests.get("https://api.spotify.com/v1/playlists/" + playlist_id + "/tracks", headers=authorization_header).text)
        tracks = tracks["items"]

        #for each track in playlist:
        #add track_id and artist_id to appropriate lists
        for i in range(0,len(tracks)):
            track_ids.append(tracks[i]["track"]["id"])
            artist_ids.append(tracks[i]["track"]["album"]["artists"][0]["id"])
            artist_name = tracks[i]["track"]["album"]["artists"][0]["name"]
            #update artist_counts in dictionary with artist_name
            try:
                artist_counts[artist_name] = artist_counts[artist_name] + 1
            except KeyError:
                artist_counts[artist_name] = 1
        #map list of track ids and artist counts to dictionaries with key as the year
        songid_dict[year] = track_ids
        artists_dict[year] = artist_counts

        #get genre information from list of artists
        #update genre_counts dictionary
        for a in artist_ids:
            try:
                genres = json.loads(requests.get("https://api.spotify.com/v1/artists/" + a, headers=authorization_header).text)["genres"]
                for g in genres:
                    try:
                        genre_counts[g] = genre_counts[g] + 1
                    except KeyError:
                        genre_counts[g] = 1
            except KeyError:
                pass
        #update genres_dict with genre_counts dictionary
        genres_dict[year] = genre_counts

    #get 2020 data from past six months' top tracks
    #limited to 50 tracks (playlists were 100 tracks long)
    try:
        this_year = json.loads(requests.get("https://api.spotify.com/v1/me/top/tracks?time_range=medium_term&limit=50&offset=0", headers=authorization_header).text)["items"]
    except KeyError:
        this_year = json.loads(requests.get("https://api.spotify.com/v1/me/top/tracks?time_range=medium_term&limit=50&offset=0", headers=authorization_header).text)["items"]

    track_ids = []
    artist_ids = []
    genre_counts = {}
    artist_counts = {}

    for i in range(0, len(this_year)):
        track_ids.append(this_year[i]["id"])
        artist_id = this_year[i]["album"]["artists"][0]["id"]
        artist_ids.append(artist_id)
        artist_name = this_year[i]["album"]["artists"][0]["name"]
        try:
            artist_counts[artist_name] = artist_counts[artist_name] + 1
        except KeyError:
            artist_counts[artist_name] = 1
        
    for a in artist_ids:
        #update genres_dict with genre_counts dictionary
        try:
            genres = json.loads(requests.get("https://api.spotify.com/v1/artists/" + a, headers=authorization_header).text)["genres"]
        except KeyError:
            pass
        for g in genres:
            try:
                genre_counts[g] = genre_counts[g] + 1
            except KeyError:
                genre_counts[g] = 1
        

    genres_dict['2020'] = genre_counts
    songid_dict['2020'] = track_ids
    artists_dict['2020'] = artist_counts

    audio_features = {}

    for year in songid_dict.keys():
        #get audio features by year

        danceability_sum = 0
        valence_sum = 0
        tempo_sum = 0
        loudness_sum = 0
        count = 0

        for song in songid_dict[year]:
            try:
                count+=1
                audiofeatures = json.loads(requests.get("https://api.spotify.com/v1/audio-features/"+song, headers=authorization_header).text)
                danceability_sum+=audiofeatures['danceability']
                valence_sum+=audiofeatures['valence']
                tempo_sum+=audiofeatures['tempo']
                loudness_sum+=audiofeatures['loudness']
            except KeyError:
                pass
        audio_dict = {'danceability':danceability_sum/count,'valence':valence_sum/count,'tempo':tempo_sum/count,'loudness':loudness_sum/count}
        audio_features[year]=audio_dict

    final_dict = {'audio_features':audio_features,'artists':artists_dict,'genres':genres_dict}
    return(final_dict)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)