import requests
from flask import Flask, request, redirect, g, render_template, url_for, session
from urllib.parse import quote
import json
import io
import base64
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

app = Flask(__name__)
app.secret_key = "super secret key"

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

        artist_ids_str = ""
        artist_ids_str_2 = ""

        #TODO: see if list splitting actually worked
        for a in range(50):
            try:
                artist_ids_str += artist_ids[a]
                artist_ids_str += ","
            except IndexError:
                pass
        if len(artist_ids) > 50:
            for a in range(50):
                try:
                    artist_ids_str_2 += artist_ids[a+50]
                    artist_ids_str_2 += ","
                except IndexError:
                    pass
            artist_ids_str_2 = artist_ids_str_2[:-1]
        artist_ids_str = artist_ids_str[:-1]
        

        genres_request = requests.get("http://api.spotify.com/v1/artists?ids=" + artist_ids_str, headers=authorization_header)

        list_of_artists = genres_request.json()["artists"]
        for i in range(0,len(list_of_artists)):
            genres = list_of_artists[i]["genres"]
            for g in genres:
                try:
                    genre_counts[g] = genre_counts[g] + 1
                except KeyError:
                    genre_counts[g] = 1
        if len(artist_ids_str_2) > 1:
            genres_request = requests.get("http://api.spotify.com/v1/artists?ids=" + artist_ids_str_2, headers=authorization_header)
            for i in range(0,len(list_of_artists)):
                genres = list_of_artists[i]["genres"]
                for g in genres:
                    try:
                        genre_counts[g] = genre_counts[g] + 1
                    except KeyError:
                        genre_counts[g] = 1

        #update genres_dict with genre_counts dictionary
        genres_dict[year] = genre_counts

    try:
        this_year_request = requests.get("https://api.spotify.com/v1/me/top/tracks?time_range=medium_term&limit=50&offset=0", headers=authorization_header)
        this_year = json.loads(this_year_request.text)["items"]
    except KeyError:
        print("Error at 2020 access: " + str(this_year_request))

    track_ids = []
    artist_ids = []
    genre_counts = {}

    for i in range(0, len(this_year)):
        track_ids.append(this_year[i]["id"])
        artist_id = this_year[i]["album"]["artists"][0]["id"]
        artist_ids.append(artist_id)

    artist_ids_str = ""
    for a in artist_ids:
        artist_ids_str += a
        artist_ids_str += ","
    artist_ids_str = artist_ids_str[:-1]    

    genres_request = requests.get("http://api.spotify.com/v1/artists?ids=" + artist_ids_str, headers=authorization_header)
    list_of_artists = genres_request.json()['artists']

    for i in range(0,len(list_of_artists)):
        genres = list_of_artists[i]["genres"]
        for g in genres:
            try:
                genre_counts[g] = genre_counts[g] + 1
            except KeyError:
                genre_counts[g] = 1
        
    genres_dict['2020'] = genre_counts
    songid_dict['2020'] = track_ids
    artist_counts = {}
    artists_request = requests.get("https://api.spotify.com/v1/me/top/artists?time_range=medium_term&limit=5", headers=authorization_header)
    for i in range(5):
        artist = artists_request.json()['items'][i]['name']
        artist_counts[artist] = 10-i
    artists_dict['2020'] = artist_counts
    audio_features = {}

    for year in songid_dict.keys():
        #get audio features by year

        danceability_sum = 0
        valence_sum = 0
        energy_sum = 0
        acousticness_sum = 0
        count = 0
        songstr = ""
        songstr2 = ""
        for i in range(50):
            try:
                songstr += songid_dict[year][i]
                songstr += ","
            except IndexError:
                pass
        if len(songid_dict[year]) > 50:
            for i in range(50):
                try:
                    songstr2 += songid_dict[year][i+50]
                    songstr2 += ","
                except IndexError:
                    pass

        songstr = songstr[:-1]
        songstr2 = songstr2[:-1]
        audiofeatures_request = requests.get("https://api.spotify.com/v1/audio-features/?ids="+songstr,headers=authorization_header)
        
        audiofeatures = audiofeatures_request.json()["audio_features"]
        
        for af in audiofeatures:
            count += 1
            danceability_sum += af["danceability"]
            valence_sum += af["valence"]
            energy_sum += af["energy"]
            acousticness_sum += af["acousticness"]

        audio_dict = {'danceability':danceability_sum/count,'valence':valence_sum/count,'energy':energy_sum/count,'acousticness':acousticness_sum/count}
        audio_features[year]=audio_dict
        if len(songstr2) > 1:
            audiofeatures_request = requests.get("https://api.spotify.com/v1/audio-features/?ids="+songstr2,headers=authorization_header)
            audiofeatures = audiofeatures_request.json()["audio_features"]

            for af in audiofeatures:
                count += 1
                danceability_sum += af["danceability"]
                valence_sum += af["valence"]
                energy_sum += af["energy"]
                acousticness_sum += af["acousticness"]

    final_dict = {'audio_features':audio_features,'artists':artists_dict,'genres':genres_dict}

    display_dict = {}
    for i in final_dict['audio_features'].keys():
        display_dict[i] = {}
    for y in display_dict.keys():
        display_dict[y]['danceability'] = final_dict['audio_features'][y]['danceability']
        display_dict[y]['valence'] = final_dict['audio_features'][y]['valence']
        display_dict[y]['acousticness'] = final_dict['audio_features'][y]['acousticness']
        display_dict[y]['energy'] = final_dict['audio_features'][y]['energy']
        display_dict[y]['artists'] = sorted(final_dict['artists'][y], key=final_dict['artists'][y].get, reverse=True)[:5]
        display_dict[y]['genres'] = sorted(final_dict['genres'][y], key=final_dict['genres'][y].get, reverse=True)[:5]

    session['year'] = '2020'
    session['display_dict'] = display_dict
    session['latest_year'] = 2020
    minyear = 2021
    for i in display_dict.keys():
        if int(i) < minyear:
            minyear = int(i)
    session['earliest_year'] = minyear
    return(redirect(url_for('display')))

@app.route("/display")
def display():
    y = session.get("year", None)
    d = session.get("display_dict", None)

    valence_average = 0.5059
    energy_average = 0.6121
    danceability_average = 0.5746
    acousticness_average = 0.2204

    v = 100*(float(d[y]['valence']))/(valence_average)
    if v > 100:
        valence_text = str(int(v-100)) + str(chr(37)) + " more"
    else:
        valence_text = str(int(100-v)) + str(chr(37)) + " less"

    e = 100*(float(d[y]['energy']))/(energy_average)  
    if e > 100:
        energy_text = str(int(e-100)) + str(chr(37)) + " more"
    else:
        energy_text = str(int(100-e)) + str(chr(37)) + " less"

    da = 100*(float(d[y]['danceability']))/(danceability_average)  
    if da > 100:
        danceability_text = str(int(da-100)) + str(chr(37)) + " more"
    else:
        danceability_text = str(int(100-da)) + str(chr(37)) + " less"

    a = 100*(float(d[y]['acousticness']))/(acousticness_average)  
    if a > 100:
        acousticness_text = str(int(a-100)) + str(chr(37)) + " more"
    else:
        acousticness_text = str(int(100-a)) + str(chr(37)) + " less"

    art = d[y]['artists']
    gen = d[y]['genres']

    image_urls = {}

    for feature in ["acousticness", "danceability", "energy", "valence"]:
        img = io.BytesIO()
        years = []
        values = []
        for year in d.keys():
            years.append(year)
            values.append(d[year][feature])

        sns.set_style("whitegrid", {'axes.grid' : False, 'axes.facecolor':'#1DB954', 'axes.edgecolor':'#3A1DB9', 'axes.spines.left': True, 'axes.spines.bottom': False, 'axes.spines.right': False, 'axes.spines.top': False})
        plt.plot(years, values)
        plt.scatter(years[int(y) - 2021], values[int(y) - 2021], color="white")
        plt.savefig(img, format='png')
        plt.close()
        img.seek(0)

        image_urls[feature] = quote(base64.b64encode(img.read()).decode())

    return(render_template("output.html", acousticness_url=image_urls['acousticness'], danceability_url=image_urls['danceability'], energy_url=image_urls['energy'], valence_url=image_urls['valence'], year=y, valence_text=valence_text, energy_text=energy_text, danceability_text = danceability_text,  acousticness_text = acousticness_text, artist1=art[0], artist2=art[1], artist3=art[2], artist4=art[3], artist5=art[4], genre1=gen[0], genre2=gen[1], genre3=gen[2], genre4=gen[3], genre5=gen[4]))

@app.route("/formback", methods=['GET', 'POST'])
def formback():
    if request.method == 'POST':
        if int(session.get("year", None)) != session.get("earliest_year", None):
            session['year'] = str(int(session.get("year", None)) - 1)
            return redirect(url_for('display'))
        else:
            return redirect(url_for('display'))

@app.route("/formforward", methods=['GET', 'POST'])
def formforward():
    if request.method == 'POST':
        if int(session.get("year", None)) != session.get("latest_year", None):
            session['year'] = str(int(session.get("year", None)) + 1)
            return redirect(url_for('display'))
        else:
            return redirect(url_for('display'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)