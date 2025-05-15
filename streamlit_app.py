import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Rooster Impact Simulator", layout="wide")

st.title("Onderwijsrooster Simulatie bij Locatie-uitval")

st.markdown("""
Deze tool voert simulaties uit op het onderwijsrooster wanneer onderwijsruimtes of gebouwen niet langer beschikbaar zijn vanaf een bepaalde datum. Het vergelijkt benodigde groepsgroottes met capaciteit van beschikbare ruimtes en toont welke activiteiten niet meer geplaatst kunnen worden.
""")

# --- Uploads ---
st.header("1. Upload gegevens")

rooster_file = st.file_uploader("Upload roosterbestand (bijv. 'All Schedule activities')", type=["csv", "xlsx"])
locaties_file = st.file_uploader("Upload locatiebestand met capaciteiten (bijv. 'Dataset All locations and maximum group size')", type=["csv", "xlsx"])

if rooster_file and locaties_file:
    # Load files
    def read_file(f):
        if f.name.endswith(".csv"):
            return pd.read_csv(f)
        else:
            return pd.read_excel(f)

    rooster_df = read_file(rooster_file)
    locaties_df = read_file(locaties_file)

    # Normaliseer kolomnamen (voor uniformiteit)
    rooster_df.columns = rooster_df.columns.str.lower()
    locaties_df.columns = locaties_df.columns.str.lower()

    # --- Instellingen selectie ---
    st.header("2. Selecteer locaties/gebouwen die niet beschikbaar zijn")

    locaties_df['gebouw'] = locaties_df['ruimte'].str.extract(r'(^[A-Za-z]+)')  # Veronderstel dat 'ruimte' kolomnamen zoals 'A1.01' heeft
    unieke_gebouwen = sorted(locaties_df['gebouw'].dropna().unique())
    unieke_locaties = sorted(locaties_df['ruimte'].dropna().unique())

    geselecteerde_gebouwen = st.multiselect("Selecteer gebouwen die niet beschikbaar zijn", unieke_gebouwen)
    geselecteerde_locaties = st.multiselect("Of selecteer specifieke locaties", unieke_locaties)
    vanaf_datum = st.date_input("Vanaf welke datum zijn deze locaties niet beschikbaar?", datetime.today())

    # Combineer gekozen ruimtes
    ruimtes_te_verwijderen = set(locaties_df[locaties_df['gebouw'].isin(geselecteerde_gebouwen)]['ruimte']) | set(geselecteerde_locaties)

    # --- Simulatie ---
        # --- Simulatie ---
    st.header("3. Simuleer impact op rooster")

    herverdeling_toestaan = st.checkbox("Sta herverdeling toe naar andere tijdstippen/dagen")

    if st.button("Voer simulatie uit"):
        rooster_df['startdatum'] = pd.to_datetime(rooster_df['startdatum'], errors='coerce')
        rooster_df['einddatum'] = pd.to_datetime(rooster_df['einddatum'], errors='coerce')

        conflicten = rooster_df[
            (rooster_df['ruimte'].isin(ruimtes_te_verwijderen)) &
            (rooster_df['startdatum'] >= pd.to_datetime(vanaf_datum))
        ]

        locaties_cap = locaties_df.set_index('ruimte')['capaciteit'].to_dict()
        rooster_df['capaciteit'] = rooster_df['ruimte'].map(locaties_cap)
        rooster_df['capaciteit'] = pd.to_numeric(rooster_df['capaciteit'], errors='coerce')
        rooster_df['groepgrootte'] = pd.to_numeric(rooster_df['groepgrootte'], errors='coerce')

        beschikbare_locaties = locaties_df[~locaties_df['ruimte'].isin(ruimtes_te_verwijderen)]
        geplande_slots = set(zip(rooster_df['ruimte'], rooster_df['startdatum'], rooster_df['einddatum']))

        herplaatsbare = []
        niet_herplaatsbaar = []
        herverdeeld = []

        for _, row in conflicten.iterrows():
            benodigde = row['groepgrootte']
            gevonden = False

            # Probeer eerst zelfde tijd in andere ruimte
            mogelijke = beschikbare_locaties[beschikbare_locaties['capaciteit'] >= benodigde]
            for _, ruimte_row in mogelijke.iterrows():
                ruimte = ruimte_row['ruimte']
                slot = (ruimte, row['startdatum'], row['einddatum'])
                if slot not in geplande_slots:
                    row_c = row.copy()
                    row_c['nieuwe_ruimte'] = ruimte
                    row_c['nieuwe_start'] = row['startdatum']
                    row_c['nieuwe_eind'] = row['einddatum']
                    herplaatsbare.append(row_c)
                    geplande_slots.add(slot)
                    gevonden = True
                    break

            if not gevonden and herverdeling_toestaan:
                # Probeer andere tijdslot
                for dagverschuiving in range(1, 8):  # 1 tot 7 dagen later
                    nieuwe_start = row['startdatum'] + pd.Timedelta(days=dagverschuiving)
                    nieuwe_eind = row['einddatum'] + pd.Timedelta(days=dagverschuiving)
                    for _, ruimte_row in mogelijke.iterrows():
                        ruimte = ruimte_row['ruimte']
                        slot = (ruimte, nieuwe_start, nieuwe_eind)
                        if slot not in geplande_slots:
                            row_c = row.copy()
                            row_c['nieuwe_ruimte'] = ruimte
                            row_c['nieuwe_start'] = nieuwe_start
                            row_c['nieuwe_eind'] = nieuwe_eind
                            herverdeeld.append(row_c)
                            geplande_slots.add(slot)
                            gevonden = True
                            break
                    if gevonden:
                        break

            if not gevonden:
                niet_herplaatsbaar.append(row)

        # --- Resultaten ---
        st.subheader("Resultaten simulatie")
        st.markdown(f"""
        - Totaal aantal getroffen activiteiten: **{len(conflicten)}**
        - Herplaatsbaar op zelfde tijd: **{len(herplaatsbare)}**
        - Herverdeeld op andere tijd/dag: **{len(herverdeeld)}**
        - Niet herplaatsbaar: **{len(niet_herplaatsbaar)}**
        """)

        if herverdeeld:
            st.subheader("Herverdeelde activiteiten (nieuwe tijd/locatie)")
            herver_df = pd.DataFrame(herverdeeld)
            st.dataframe(herver_df[['activiteit', 'ruimte', 'startdatum', 'groepgrootte', 'nieuwe_ruimte', 'nieuwe_start']])

        if niet_herplaatsbaar:
            st.subheader("Niet herplaatsbare activiteiten")
            niet_df = pd.DataFrame(niet_herplaatsbaar)
            st.dataframe(niet_df[['activiteit', 'ruimte', 'startdatum', 'einddatum', 'groepgrootte']])
            csv = niet_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download niet-herplaatsbare activiteiten", csv, "niet_herplaatsbaar.csv", "text/csv")
