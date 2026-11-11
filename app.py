import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from markets import MARKETS
from live_data import fetch_price, fetch_leaders
from engine import compute
from dominance import detect, event_study, ShiftConfig

st.set_page_config(page_title='Market Emotion Radar | CAC 40 & Nasdaq 100',page_icon='📡',layout='wide')
st.title('📡 Market Emotion Radar — CAC 40 & Nasdaq 100')
st.caption('MER v0.4 · Dominance Shift Detector · Données Yahoo non garanties temps réel · Signaux expérimentaux')

@st.cache_data(ttl=240,show_spinner=False)
def cached_price(key,days):return fetch_price(MARKETS[key],days)

@st.cache_data(ttl=300,show_spinner=False)
def cached_leaders(key,days):return fetch_leaders(MARKETS[key],days)

market_name=st.sidebar.radio('Marché',list(MARKETS),index=0)
market=MARKETS[market_name]
source=st.sidebar.radio('Données',['Yahoo + échantillon de valeurs','Yahoo — instrument seul','Importer CSV'],index=0)
days=st.sidebar.slider('Historique (jours)',2,7,5)
auto=st.sidebar.toggle('Actualiser toutes les 5 minutes',value=True)
if st.sidebar.button('🔄 Forcer le rafraîchissement'):
    cached_price.clear();cached_leaders.clear();st.rerun()
threshold=st.sidebar.slider('Variation MER sur 10 min',6,20,8)
cost_bps=st.sidebar.slider('Coût aller-retour simulé (bps)',0.0,20.0,3.0,0.5)
st.sidebar.info('Le CAC est représenté par un ETF coté (C40.PA), pas directement par l’indice ^FCHI. Les cours Yahoo peuvent être différés. Vérifier la disponibilité et le volume.')

@st.fragment(run_every='300s' if auto else None)
def dashboard():
    try:
        constituents=None
        if source=='Importer CSV':
            price_file=st.file_uploader(f'{market.symbol} : timestamp,open,high,low,close,volume',type='csv',key=f'price_{market.key}')
            constituents_file=st.file_uploader('Constituants (facultatif) : timestamp + prix par titre',type='csv',key=f'leaders_{market.key}')
            if price_file is None:
                st.info('Charge un CSV pour afficher le marché.');return
            def parse(file):
                frame=pd.read_csv(file)
                frame['timestamp']=pd.to_datetime(frame['timestamp'],utc=True).dt.tz_convert(market.timezone)
                return frame.set_index('timestamp').sort_index()
            price=parse(price_file)
            if constituents_file is not None:constituents=parse(constituents_file)
        else:
            with st.spinner(f'Chargement de {market.name}…'):
                price=cached_price(market_name,days)
                if source=='Yahoo + échantillon de valeurs':
                    try:constituents=cached_leaders(market_name,days)
                    except Exception as exc:st.warning(f'Constituants indisponibles : {exc}. Repli sur un proxy de breadth non indépendant.')
        if price.empty:raise ValueError('Aucune bougie de marché disponible.')
        if (price.volume<=0).all():
            st.error('Aucun volume exploitable pour cet instrument : le MER ne peut pas être calculé de façon fiable.');return
        result=detect(compute(price,constituents,market),ShiftConfig(threshold=float(threshold)),timezone=market.timezone)
        if result.empty:raise ValueError('Aucune bougie en séance régulière.')
        dates=sorted(set(result.index.tz_convert(market.timezone).date))
        today=pd.Timestamp.now(tz=market.timezone).date()
        selected_date=st.selectbox(f'Séance ({market.timezone})',dates,index=len(dates)-1,key=f'date_{market.key}')
        selected=result[result.index.tz_convert(market.timezone).date==selected_date]
        valid=selected.dropna(subset=['MER'])
        if valid.empty:
            st.warning('Pas assez de bougies pour calculer le MER. Attends le début de la séance et la période de stabilisation.');return
        last=valid.iloc[-1];stamp=valid.index[-1]
        now=pd.Timestamp.now(tz=market.timezone)
        age=(now-stamp).total_seconds()/60
        if selected_date!=today:
            st.warning('⚠️ Données d’une séance précédente : ne pas interpréter comme un signal actuel.')
        elif age>15:
            st.warning(f'⚠️ Dernière bougie vieille de {age:.0f} minutes : données différées ou marché fermé.')
        if constituents is not None:
            st.info(f'Breadth calculé sur {constituents.shape[1]} titres disponibles (échantillon non pondéré, pas tous les constituants).')
        else:
            st.info('Breadth approximé à partir de l’instrument seul : ce n’est pas une confirmation indépendante.')
        st.caption(f'Instrument : **{market.symbol}** · Séance : {market.start}–{market.end} ({market.timezone}) · Dernière bougie : {stamp.strftime("%d/%m/%Y %H:%M %Z")}')
        cols=st.columns(4)
        cols[0].metric('MER · 0–100',f'{last.MER:.1f}')
        cols[1].metric('Vitesse · 15 min',f'{last.velocity_15m:+.1f}' if pd.notna(last.velocity_15m) else '—')
        cols[2].metric('Dominance',last.shift_state)
        cols[3].metric(market.symbol,f'{last.close:.2f} {market.currency}')
        if pd.notna(last.delta_10m) and pd.notna(last.rvol):
            st.caption(f'ΔMER 10 min : {last.delta_10m:+.1f} · Breadth : {last.breadth:+.2f} · Volume relatif : {last.rvol:.2f}×')
        is_fresh=(selected_date==today and 0<=age<=15)
        if last.shift_signal in ('LONG','SHORT') and is_fresh:
            st.warning(f'⚡ Basculement {last.shift_signal} à la clôture de la dernière bougie. Signal expérimental, non exécutable rétroactivement.')
        elif last.shift_signal in ('LONG','SHORT'):
            st.info(f'Dernier signal historique : {last.shift_signal}. Il ne s’agit PAS d’une alerte actuelle.')
        else:st.info('Pas de nouveau basculement confirmé sur la dernière bougie.')
        fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.58,.42],vertical_spacing=.08)
        fig.add_trace(go.Scatter(x=selected.index,y=selected.close,name=market.symbol,line_color='#6b9feb'),row=1,col=1)
        fig.add_trace(go.Scatter(x=selected.index,y=selected.MER,name='MER',line_color='#e7a84f'),row=2,col=1)
        for level in (40,50,60):fig.add_hline(y=level,row=2,col=1,line_dash='dot',line_color='gray',opacity=.45)
        for signal,color,symbol in [('LONG','#2ab57c','triangle-up'),('SHORT','#e65a66','triangle-down')]:
            points=selected[selected.shift_signal==signal]
            fig.add_trace(go.Scatter(x=points.index,y=points.MER,mode='markers',name=signal,marker={'color':color,'symbol':symbol,'size':11}),row=2,col=1)
        fig.update_layout(height=580,hovermode='x unified',legend_orientation='h',margin=dict(l=10,r=10,t=20,b=10))
        fig.update_yaxes(title_text=f'{market.symbol} ({market.currency})',row=1,col=1)
        fig.update_yaxes(title_text='MER',range=[0,100],row=2,col=1)
        st.plotly_chart(fig,use_container_width=True)
        st.subheader('Décomposition du dernier score')
        st.dataframe(pd.DataFrame({'Composante':['Breadth','Momentum','Pression-volume','VWAP'],
                                  'Valeur':[last.breadth,last.momentum,last.volume_pressure,last.vwap_signal],
                                  'Poids':[.35,.30,.20,.15]}),hide_index=True,use_container_width=True)
        st.subheader('Journal des basculements')
        history=selected[selected.shift_signal.isin(['LONG','SHORT'])][['shift_signal','MER','delta_10m','breadth','rvol','close']]
        st.dataframe(history.tail(30).sort_index(ascending=False),use_container_width=True)
        with st.expander('Étude événementielle — simulation'):
            summary,details=event_study(result,cost_bps=cost_bps,timezone=market.timezone)
            st.dataframe(summary,hide_index=True,use_container_width=True)
            st.caption('Entrée simulée à l’ouverture de la bougie suivante, sortie à +5/+10/+15/+30 min dans la même séance. Les frais sont illustratifs. Les signaux ne sont pas statistiquement validés.')
            if not details.empty:
                st.download_button('⬇️ Exporter les événements',details.to_csv(index=False).encode(),file_name=f'mer_{market.key}_events.csv',mime='text/csv')
        st.download_button('⬇️ Exporter les scores',result.to_csv().encode(),file_name=f'mer_{market.key}_scores.csv',mime='text/csv')
    except Exception as exc:
        st.error(f'Impossible de charger {market.name} : {exc}')
        st.info('Yahoo Finance peut être retardé ou bloqué. Tu peux utiliser un CSV de bougies 5 minutes.')

dashboard()
st.divider()
st.caption('Données Yahoo non garanties temps réel. Un ETF ne reproduit pas exactement l’indice et ses volumes diffèrent. Le MER est un indicateur heuristique, pas une mesure directe de la peur ou de l’avidité. Signaux expérimentaux : pas de conseil de trading.')
