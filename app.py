import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from engine import compute, evaluate
from live_data import fetch_qqq, fetch_leaders, LEADERS

st.set_page_config(page_title='Market Emotion Radar | Nasdaq 100', page_icon='📡', layout='wide')
st.title('📡 Market Emotion Radar — Nasdaq 100')
st.caption('MER v0.2 · Actualisation automatique · Signaux expérimentaux · Ne constitue pas un conseil financier')

@st.cache_data(ttl=240, show_spinner=False)
def cached_qqq(days): return fetch_qqq(days)

@st.cache_data(ttl=300, show_spinner=False)
def cached_leaders(days): return fetch_leaders(days)

st.sidebar.header('Configuration')
source = st.sidebar.radio('Source', ['Yahoo Finance — QQQ', 'Yahoo + échantillon Nasdaq-100', 'Importer CSV'], index=1)
days = st.sidebar.slider('Historique (jours)', 2, 7, 5)
auto = st.sidebar.toggle('Actualiser toutes les 5 minutes', value=True)
if st.sidebar.button('🔄 Forcer le rafraîchissement'):
    cached_qqq.clear()
    cached_leaders.clear()
    st.rerun()
st.sidebar.info('Yahoo Finance peut être différé, limité ou indisponible. Le score mesure des proxys de pression de marché, pas des émotions observables.')

@st.fragment(run_every='300s' if auto else None)
def dashboard():
    try:
        constituents = None
        if source == 'Importer CSV':
            qfile = st.file_uploader('QQQ OHLCV : timestamp,open,high,low,close,volume', type='csv')
            cfile = st.file_uploader('Constituants (optionnel) : timestamp + colonnes de prix', type='csv')
            if qfile is None:
                st.info('Importe un CSV QQQ pour afficher le MER.')
                return
            def parse(f):
                df = pd.read_csv(f)
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('America/New_York')
                return df.set_index('timestamp').sort_index()
            qqq = parse(qfile)
            if cfile: constituents = parse(cfile)
        else:
            with st.spinner('Récupération des données intrajournalières…'):
                qqq = cached_qqq(days)
                if source == 'Yahoo + échantillon Nasdaq-100':
                    try:
                        constituents = cached_leaders(days)
                    except Exception as exc:
                        st.warning(f'Échantillon indisponible ({exc}). Repli sur le proxy QQQ.')
        result = compute(qqq, constituents)
        if result.empty: raise ValueError('Aucune barre de séance disponible.')
        dates = sorted(set(result.index.date))
        today = pd.Timestamp.now(tz='America/New_York').date()
        selected_date = st.selectbox('Séance (heure de New York)', dates, index=len(dates)-1)
        selected = result[result.index.date == selected_date]
        valid = selected.dropna(subset=['MER'])
        if valid.empty:
            st.warning('Pas assez de barres complètes pour calculer le MER. Réessaie après les premières minutes de séance.')
            return
        last = valid.iloc[-1]
        stamp = valid.index[-1]
        if selected_date != today:
            st.warning('⚠️ Dernière séance disponible : ce ne sont PAS des données de la séance actuelle.')
        else:
            age = (pd.Timestamp.now(tz='America/New_York') - stamp).total_seconds()/60
            if age > 15:
                st.warning(f'⚠️ Dernière barre vieille de {age:.0f} minutes. Données potentiellement différées ou marché fermé.')
        if constituents is not None:
            st.info(f'Breadth sur un échantillon de {constituents.shape[1]} grandes valeurs Nasdaq-100 (non pondéré), PAS les 100 titres.')
        else:
            st.info('Breadth = proxy QQQ ; pas de mesure indépendante des constituants.')
        st.caption(f'Dernière barre : **{stamp.strftime("%d/%m/%Y %H:%M %Z")}** · Source : {source} · Données non garanties en temps réel')
        cols = st.columns(4)
        cols[0].metric('MER · 0–100', f'{last.MER:.1f}', help='Score heuristique, non calibré')
        cols[1].metric('Vitesse · 15 min', f'{last.velocity_15m:+.1f}' if pd.notna(last.velocity_15m) else '—')
        cols[2].metric('Signal', {'neutral':'Neutre','bullish_reversal':'Reprise acheteuse ?','bearish_reversal':'Reprise vendeuse ?'}.get(last.signal, last.signal))
        cols[3].metric('QQQ', f'${last.close:.2f}')
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.58,.42], vertical_spacing=.08)
        fig.add_trace(go.Scatter(x=selected.index, y=selected.close, name='QQQ', line_color='#6b9feb'), row=1, col=1)
        fig.add_trace(go.Scatter(x=selected.index, y=selected.MER, name='MER', line_color='#e7a84f'), row=2, col=1)
        for level in [40,50,60]: fig.add_hline(y=level, row=2, col=1, line_dash='dot', line_color='gray', opacity=.45)
        for signal,color,symbol in [('bullish_reversal','#2ab57c','triangle-up'),('bearish_reversal','#e65a66','triangle-down')]:
            pts=selected[selected.signal==signal]
            fig.add_trace(go.Scatter(x=pts.index,y=pts.MER,mode='markers',name=signal,marker={'color':color,'symbol':symbol,'size':11}),row=2,col=1)
        fig.update_layout(height=580, hovermode='x unified', legend_orientation='h', margin=dict(l=10,r=10,t=20,b=10))
        fig.update_yaxes(title_text='QQQ ($)',row=1,col=1)
        fig.update_yaxes(title_text='MER',range=[0,100],row=2,col=1)
        st.plotly_chart(fig,use_container_width=True)
        st.subheader('Décomposition du dernier score')
        st.dataframe(pd.DataFrame({'Composante':['Breadth','Momentum','Pression-volume','VWAP'], 'Valeur':[last.breadth,last.momentum,last.volume_pressure,last.vwap_signal], 'Poids':[.35,.30,.20,.15]}),hide_index=True,use_container_width=True)
        with st.expander('Évaluation exploratoire des signaux'):
            st.dataframe(evaluate(result),hide_index=True,use_container_width=True)
            st.caption('Aucune validation hors échantillon ni frais de transaction : pas une performance de trading.')
        st.download_button('⬇️ Exporter les scores CSV',result.to_csv().encode(),file_name='mer_nasdaq100.csv',mime='text/csv')
    except Exception as exc:
        st.error(f'Impossible de charger le marché : {exc}')
        st.info('Vérifie ta connexion, réessaie après quelques minutes ou utilise le mode CSV. Yahoo peut bloquer les serveurs cloud.')

dashboard()
st.divider()
st.caption('MER = 50 + 50 × (0,35 breadth + 0,30 momentum + 0,20 volume + 0,15 VWAP). Signaux heuristiques. Horaires : séance régulière US, barres de 5 minutes. Jours fériés et clôtures anticipées non encore gérés.')
