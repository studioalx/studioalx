import streamlit as st
from streamlit_folium import folium_static
import folium
#import numpy as np
import pandas as pd
#import os
#import plost

st.set_page_config(layout="wide")

#https://en.wikipedia.org/wiki/Forest_Landscape_Integrity_Index
with st.expander("Lion coalitions and lion prides. Expand to read more..."):
	st.title('Proof-of-concept Lion Map')
	st.write("""
	## Lion coalitions and lion prides
	NOTE: map is in the ealry alpha version, names, images and positions are only place holders 
	""")

#choice = st.sidebar.radio(
#    "Features (place holder)",
#    ("Male Lions", "Prides", "Lionesses", "All"))

st.sidebar.write(' # Example filters:')
st.sidebar.write(' ## Alive:')
prides = st.sidebar.checkbox('Prides')
male_lions = st.sidebar.checkbox('Male lions')
lionesses = st.sidebar.checkbox('Lionesses')
all_data = st.sidebar.checkbox('All')

st.sidebar.write(' ## Deceased:')
dead_male_lions = st.sidebar.checkbox('Male lions (R.I.P.)')
dead_lionesses = st.sidebar.checkbox('Lionesses (R.I.P.)')

#for lat,lon,name,perc in zip(df['lat'],df['long'],df['ix_name'],df['perc']):
#https://stackoverflow.com/questions/62091003/folium-popup-text-issue-for-overlapping-coordinatesupdatehtml-source-code

m = folium.Map(location=[-24.687117658472058,31.522959762553785], zoom_start=10, tiles="OpenStreetMap") #Stamen Terrain

df_prides = pd.read_csv('prides.csv')

#if choice == "Prides":
if prides:

	for i in range(len(df_prides['Pride'])):

	#	custom_icon = folium.CustomIcon(lions_png, icon_size=(75, 75), popup_anchor=(0, -22))
		coalition = df_prides['Coalition'][i]
		pride = df_prides['Pride'][i]
		you_post = df_prides['You_post'][i]

		lon = df_prides['Lon'][i]
		lat = df_prides['Lat'][i]

		website = you_post # repetition - remove
		directions = 'direction'
		coordinates = [lon, lat]

		pub_html = folium.Html(f"""<p style="text-align: center;"><span style="font-family: Didot, serif; font-size: 21px;">{pride} pride</span></p>
			<p style="text-align: center;"><iframe width="280" height="157" src={you_post} title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
			<p style="text-align: center;"><span style="font-family: Didot, serif; font-size: 17px;">{coalition} - dominant coalition</span></p>
			<p style="text-align: center;"><a href={directions} target="_blank" title="Some link {pride}"><span style="font-family: Didot, serif; font-size: 17px;">Some link {pride}</span></a></p>
			""", script=True)
		popup = folium.Popup(pub_html, max_width=700)
			# Create marker with custom icon and pop-up.

		custom_marker = folium.Marker(location=coordinates,
			icon = folium.DivIcon(html=f"""
				    <div><svg>
				        <circle cx="30" cy="30" r="30" fill="red" opacity=".3"/>
				    </svg>></div>"""), 
			tooltip=f"{pride} pride", 
			popup=popup)

		custom_marker.add_to(m)
	


lions_png = 'lion-icon.png'
df_lions = pd.read_csv('lions.csv')

#if choice == "Male Lions":
if male_lions:

	for i in range(len(df_lions['Name'])):

		if df_lions['Sex'][i] == 'Male' and df_lions['Status'][i] == 'Alive':
			lions_png = 'lion-icon.png'
		elif df_lions['Sex'][i] == 'Female' and df_lions['Status'][i] == 'Alive':
			lions_png = 'lioness.png'
		elif df_lions['Sex'][i] == 'Female' and df_lions['Status'][i] == 'Dead':
			lions_png = 'lioness-rip.png'


		custom_icon = folium.CustomIcon(lions_png, icon_size=(48, 79), popup_anchor=(0, -22))
		name = df_lions['Name'][i]
		coalition = df_lions['Coalition'][i]
		pride = df_lions['Pride'][i]
		you_post = df_lions['You_post'][i]

		lon = df_lions['Lon'][i]
		lat = df_lions['Lat'][i]

		website = you_post # repetition - remove
		directions = 'direction'
		coordinates = [lon, lat]

		pub_html = folium.Html(f"""<p style="text-align: center;"><span style="font-family: Didot, serif; font-size: 21px;">{name} - {coalition}</span></p>
			<p style="text-align: center;"><iframe width="280" height="157" src={you_post} title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
			<p style="text-align: center;"><a href={website} target="_blank" title="{name} Website"><span style="font-family: Didot, serif; font-size: 17px;">{name} Website</span></a></p>
			<p style="text-align: center;"><a href={directions} target="_blank" title="Some link {name}"><span style="font-family: Didot, serif; font-size: 17px;">Some link or description about {name}</span></a></p>
			""", script=True)
		popup = folium.Popup(pub_html, max_width=700)
		# Create marker with custom icon and pop-up.
		custom_marker = folium.Marker(location=coordinates, icon=custom_icon, tooltip=name, popup=popup)

		custom_marker.add_to(m)


folium_static(m, width=1200, height=700)


