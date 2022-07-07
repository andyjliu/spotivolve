import requests
from flask import Flask, request, redirect, g, render_template, url_for, session
from urllib.parse import quote
import json
import io
import base64
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from datetime import date
from collections import Counter

app = Flask(__name__)
app.secret_key = "super secret key"

cid = 'ebd8cac9845048d99aca6a20739b8f89'
secret = 'c27e28a69a0d4f4c8682e99d248122c7'
# redirect_uri = "http://127.0.0.1:5000/callback/q"
redirect_uri = "https://spotivolve.herokuapp.com/callback/q"
scope = 'playlist-read-private user-top-read'

auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "scope": scope,
    "client_id": cid
}

CURRENT_YEAR = date.today().year
AVERAGE_AUDIO_FEATURE_VALUES = {"danceability":0.57, "valence":0.45, "energy":0.65, "acousticness":0.22}
AUDIO_FEATURES = ["danceability", "valence", "energy", "acousticness"]
PERCENT_SIGN_INDEX = 37
NUM_TOP = 5
MAX_SONGS_PER_CALL = 50

@app.route("/")
def index():
    return(render_template("index.html"))

@app.route("/form", methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        return redirect(url_for('authorization'))

@app.route("/authorization")
def authorization():
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

    try:
        access_token = response_data["access_token"]
        refresh_token = response_data["refresh_token"]
        token_type = response_data["token_type"]
        expires_in = response_data["expires_in"]
    except KeyError:
        print("Error on Access Token request: " + str(post_request))

    authorization_header = {"Authorization": "Bearer {}".format(access_token)}

    #searches for Spotify-made 'your top songs' playlists
    search_url = "https://api.spotify.com/v1/search?q=%22Your%20Top%20Songs%22&type=playlist"
    search = json.loads((requests.get(search_url, headers=authorization_header).text))
    playlists = search["playlists"]["items"]
    playlist_ids = []

    #filter out playlists not made by official spotify account
    for i in range(len(playlists)):
        if playlists[i]["owner"]["external_urls"]["spotify"] == "https://open.spotify.com/user/spotify":
            playlist_ids.append(playlists[i]["uri"])

    #loop over all Your Top Songs playlists
    for playlist_id in playlist_ids:
        genre_counts = {}
        artist_counts = Counter()

        #get year playlist corresponds to, as well as list of tracks it contains
        try:
            playlist_id = playlist_id.split(":")[-1]
            playlist_request = requests.get("https://api.spotify.com/v1/playlists/" + playlist_id, headers=authorization_header)
            playlist = json.loads(playlist_request.text) 
            year = playlist["name"].split(" ")[-1]
            tracks = json.loads(requests.get("https://api.spotify.com/v1/playlists/" + playlist_id + "/tracks", headers=authorization_header).text)
            tracks = tracks["items"]
        except KeyError:
            print("Error on playlist request: " + str(playlist_request))

        #for each track in playlist:
        #add track_id and artist_id to appropriate lists
        track_ids = [tracks[i]["track"]["id"] for i in range(len(tracks))]
        artist_ids = [tracks[i]["track"]["album"]["artists"][0]["id"] for i in range(len(tracks))]
        for i in range(0,len(tracks)):
            artist_name = tracks[i]["track"]["album"]["artists"][0]["name"]
            artist_counts[artist_name] += 1
        #map list of track ids and artist counts to dictionaries with key as the year
        songid_dict[year] = track_ids
        artists_dict[year] = artist_counts

        #get genre information from list of artists
        #update genre_counts dictionary
        artist_ids_str = ",".join([artist_ids[i] for i in range(min(MAX_SONGS_PER_CALL,len(artist_ids)))])
        artist_ids_str_2 = ""
        if len(artist_ids) > MAX_SONGS_PER_CALL:
            artist_ids_str_2 += ",".join([artist_ids[i] for i in range(MAX_SONGS_PER_CALL,len(artist_ids))])

        genres_request = requests.get("http://api.spotify.com/v1/artists?ids=" + artist_ids_str, headers=authorization_header)
        
        list_of_artists = genres_request.json()["artists"]
        genre_counts = sum([Counter(list_of_artists[i]["genres"]) for i in range(len(list_of_artists))], Counter())
        if len(artist_ids_str_2) > 1:
            genres_request = requests.get("http://api.spotify.com/v1/artists?ids=" + artist_ids_str_2, headers=authorization_header)
            genre_counts += sum([Counter(list_of_artists[i]["genres"]) for i in range(len(list_of_artists))], Counter())

        #update genres_dict with genre_counts dictionary
        genres_dict[year] = genre_counts

    try:
        this_year_request = requests.get("https://api.spotify.com/v1/me/top/tracks?time_range=medium_term&limit=50&offset=0", headers=authorization_header)
        this_year = json.loads(this_year_request.text)["items"]
    except KeyError:
        print("Error at " + str(CURRENT_YEAR) + " access: " + str(this_year_request))

    track_ids = [this_year[i]["id"] for i in range(len(this_year))]
    artist_ids = [this_year[i]["album"]["artists"][0]["id"] for i in range(len(this_year))]

    artist_ids_str = ",".join(artist_ids)  
    genres_request = requests.get("http://api.spotify.com/v1/artists?ids=" + artist_ids_str, headers=authorization_header)
    list_of_artists = genres_request.json()['artists']
    genre_counts = sum([Counter(list_of_artists[i]["genres"]) for i in range(len(list_of_artists))], Counter())
        
    genres_dict[str(CURRENT_YEAR)] = genre_counts
    songid_dict[str(CURRENT_YEAR)] = track_ids
    artist_counts = {}
    artists_request = requests.get(f"https://api.spotify.com/v1/me/top/artists?time_range=medium_term&limit={NUM_TOP}", headers=authorization_header)
    for i in range(NUM_TOP):
        artist = artists_request.json()['items'][i]['name']
        artist_counts[artist] = 2*NUM_TOP-i
    artists_dict[str(CURRENT_YEAR)] = artist_counts
    audio_features = {}

    for year in songid_dict.keys():
        #get audio features by year
        audio_features_dict = {}
        for feature in AUDIO_FEATURES:
            audio_features_dict[feature] = 0
        count = 0
        songstr = ",".join([songid_dict[year][i] for i in range(min(MAX_SONGS_PER_CALL,len(songid_dict[year])))])
        songstr2 = ""
        if len(songid_dict[year]) > 50:
            songstr2 += ",".join([songid_dict[year][i] for i in range(MAX_SONGS_PER_CALL,len(songid_dict[year]))])

        audiofeatures_request = requests.get("https://api.spotify.com/v1/audio-features/?ids="+songstr,headers=authorization_header)      
        audiofeatures = audiofeatures_request.json()["audio_features"]
        
        for af in audiofeatures:
            count += 1
            for feature in AUDIO_FEATURES:
                audio_features_dict[feature] += af[feature]

        if len(songstr2) > 1:
            audiofeatures_request = requests.get("https://api.spotify.com/v1/audio-features/?ids="+songstr2,headers=authorization_header)
            audiofeatures = audiofeatures_request.json()["audio_features"]
            for af in audiofeatures:
                count += 1
                for feature in AUDIO_FEATURES:
                    audio_features_dict[feature] += af[feature]
                    
        for feature in AUDIO_FEATURES:
            audio_features_dict[feature] = audio_features_dict[feature]/count         
        audio_features[year]=audio_features_dict

    final_dict = {'audio_features':audio_features,'artists':artists_dict,'genres':genres_dict}

    display_dict = {}
    for i in final_dict['audio_features'].keys():
        display_dict[i] = {}
    for y in display_dict.keys():
        for feature in AUDIO_FEATURES:
            display_dict[y][feature] = final_dict['audio_features'][y][feature]
        display_dict[y]['artists'] = sorted(final_dict['artists'][y], key=final_dict['artists'][y].get, reverse=True)[:NUM_TOP]
        display_dict[y]['genres'] = sorted(final_dict['genres'][y], key=final_dict['genres'][y].get, reverse=True)[:NUM_TOP]

    session['year'] = str(CURRENT_YEAR)
    session['display_dict'] = display_dict
    session['latest_year'] = str(CURRENT_YEAR)
    minyear = CURRENT_YEAR + 1
    for i in display_dict.keys():
        if int(i) < minyear:
            minyear = int(i)
    session['earliest_year'] = minyear
    return(redirect(url_for('display')))

@app.route("/display")
def display():
    y = session.get("year", None)
    d = session.get("display_dict", None)
    audio_feature_texts = {}
    for feature in AUDIO_FEATURES:
        percentage = 100*(float(d[y][feature]))/(AVERAGE_AUDIO_FEATURE_VALUES[feature])
        if percentage > 100:
            audio_feature_texts[feature] = str(int(percentage-100)) + str(chr(PERCENT_SIGN_INDEX)) + " more"
        else:
            audio_feature_texts[feature] = str(int(100-percentage)) + str(chr(PERCENT_SIGN_INDEX)) + " less"

    art = {i+1 : d[y]['artists'][i] for i in range(NUM_TOP)}
    gen = {i+1 : d[y]['genres'][i] for i in range(NUM_TOP)}

    image_urls = {}

    for feature in AUDIO_FEATURES:
        img = io.BytesIO()
        years = []
        values = []
        for year in d.keys():
            years.append(year)
            values.append(d[year][feature])
        sns.set_style("whitegrid", {'axes.grid' : False})
        #sns.set_style("whitegrid", {'axes.grid' : False, 'axes.facecolor':'#1DB954', 'axes.edgecolor':'#3A1DB9', 'axes.spines.left': True, 'axes.spines.bottom': False, 'axes.spines.right': False, 'axes.spines.top': False})
        plt.plot(years, values)
        plt.scatter(years[int(y) - (CURRENT_YEAR + 1)], values[int(y) - (CURRENT_YEAR + 1)], color="green")
        plt.savefig(img, format='png')
        plt.close()
        img.seek(0)

        image_urls[feature] = quote(base64.b64encode(img.read()).decode())
    return(render_template("output.html", img_urls = image_urls, year=y, feature_texts = audio_feature_texts, artists = art, genres = gen))
    # return(render_template("output.html", acousticness_url=image_urls['acousticness'], danceability_url=image_urls['danceability'], energy_url=image_urls['energy'], valence_url=image_urls['valence'], year=y, valence_text=audio_feature_texts['valence'], energy_text=audio_feature_texts['energy'], danceability_text = audio_feature_texts['danceability'],  acousticness_text = audio_feature_texts['acousticness'], artist1=art[0], artist2=art[1], artist3=art[2], artist4=art[3], artist5=art[4], genre1=gen[0], genre2=gen[1], genre3=gen[2], genre4=gen[3], genre5=gen[4]))

@app.route("/formback", methods=['GET', 'POST'])
def formback():
    if request.method == 'POST':
        if int(session.get("year", None)) != session.get("earliest_year", None):
            session['year'] = str(int(session.get("year", None)) - 1)
        return redirect(url_for('display'))

@app.route("/formforward", methods=['GET', 'POST'])
def formforward():
    if request.method == 'POST':
        if int(session.get("year", None)) != session.get("latest_year", None):
            session['year'] = str(int(session.get("year", None)) + 1)
        return redirect(url_for('display'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)