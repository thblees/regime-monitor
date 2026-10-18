"""
Aktienuniversum für den Pairs-Trading-Screener.

Paare werden nur INNERHALB eines Sektors gebildet (ökonomisch begründete
Kointegration statt Zufallstreffer). Regionen werden gemischt, d.h. auch
Cross-Region-Paare (z.B. BMW vs. GM) werden getestet und entsprechend markiert.

Ticker-Format: Yahoo Finance.
  .DE  Xetra (EUR)          .PA Paris (EUR)      .AS Amsterdam (EUR)
  .MI  Mailand (EUR)        .MC Madrid (EUR)     .BR Brüssel (EUR)
  .HE  Helsinki (EUR)       .VI Wien (EUR)       .LS Lissabon (EUR)
  .SW  Zürich (CHF)         .L  London (GBp)     .CO Kopenhagen (DKK)
  ohne Suffix: USA (USD)
"""

# sector -> [(ticker, name), ...]
UNIVERSE = {
    "Autos": [
        ("BMW.DE", "BMW"), ("MBG.DE", "Mercedes-Benz"), ("VOW3.DE", "Volkswagen Vz."),
        ("P911.DE", "Porsche AG"), ("PAH3.DE", "Porsche SE"), ("CON.DE", "Continental"),
        ("DTG.DE", "Daimler Truck"),
        ("STLAM.MI", "Stellantis"), ("RACE.MI", "Ferrari"), ("RNO.PA", "Renault"), ("ML.PA", "Michelin"),
        ("F", "Ford"), ("GM", "General Motors"), ("TSLA", "Tesla"),
    ],
    "Banken": [
        ("DBK.DE", "Deutsche Bank"), ("CBK.DE", "Commerzbank"), ("PBB.DE", "Deutsche Pfandbriefbank"),
        ("BNP.PA", "BNP Paribas"), ("ACA.PA", "Crédit Agricole"), ("GLE.PA", "Société Générale"),
        ("SAN.MC", "Banco Santander"), ("BBVA.MC", "BBVA"), ("CABK.MC", "CaixaBank"),
        ("ISP.MI", "Intesa Sanpaolo"), ("UCG.MI", "UniCredit"), ("INGA.AS", "ING"), ("KBC.BR", "KBC"),
        ("UBSG.SW", "UBS"), ("HSBA.L", "HSBC"), ("BARC.L", "Barclays"), ("LLOY.L", "Lloyds"),
        ("NWG.L", "NatWest"), ("STAN.L", "Standard Chartered"),
        ("JPM", "JPMorgan"), ("BAC", "Bank of America"), ("C", "Citigroup"), ("WFC", "Wells Fargo"),
        ("GS", "Goldman Sachs"), ("MS", "Morgan Stanley"), ("USB", "U.S. Bancorp"),
        ("PNC", "PNC Financial"), ("TFC", "Truist"), ("SCHW", "Charles Schwab"),
    ],
    "Versicherungen": [
        ("ALV.DE", "Allianz"), ("MUV2.DE", "Munich Re"), ("HNR1.DE", "Hannover Rück"), ("TLX.DE", "Talanx"),
        ("CS.PA", "AXA"), ("ZURN.SW", "Zurich Insurance"), ("SREN.SW", "Swiss Re"), ("G.MI", "Generali"),
        ("AGN.AS", "Aegon"), ("NN.AS", "NN Group"), ("PRU.L", "Prudential"), ("AV.L", "Aviva"),
        ("LGEN.L", "Legal & General"),
        ("AIG", "AIG"), ("MET", "MetLife"), ("PRU", "Prudential Financial"), ("ALL", "Allstate"),
        ("TRV", "Travelers"), ("CB", "Chubb"), ("PGR", "Progressive"), ("AFL", "Aflac"),
    ],
    "Börsen & Finanzdienste": [
        ("DB1.DE", "Deutsche Börse"), ("ENX.PA", "Euronext"), ("LSEG.L", "LSE Group"),
        ("ICE", "Intercontinental Exchange"), ("CME", "CME Group"), ("NDAQ", "Nasdaq"), ("CBOE", "Cboe"),
        ("SPGI", "S&P Global"), ("MCO", "Moody's"), ("MSCI", "MSCI"),
        ("BLK", "BlackRock"), ("BX", "Blackstone"), ("KKR", "KKR"), ("TROW", "T. Rowe Price"),
    ],
    "Zahlungsverkehr": [
        ("ADYEN.AS", "Adyen"),
        ("V", "Visa"), ("MA", "Mastercard"), ("AXP", "American Express"), ("PYPL", "PayPal"),
        ("COF", "Capital One"), ("FI", "Fiserv"), ("GPN", "Global Payments"),
    ],
    "Pharma": [
        ("BAYN.DE", "Bayer"), ("MRK.DE", "Merck KGaA"),
        ("SAN.PA", "Sanofi"), ("NOVN.SW", "Novartis"), ("ROG.SW", "Roche"), ("AZN.L", "AstraZeneca"),
        ("GSK.L", "GSK"), ("NOVO-B.CO", "Novo Nordisk"), ("UCB.BR", "UCB"),
        ("PFE", "Pfizer"), ("MRK", "Merck & Co"), ("JNJ", "Johnson & Johnson"), ("LLY", "Eli Lilly"),
        ("ABBV", "AbbVie"), ("BMY", "Bristol-Myers Squibb"), ("AMGN", "Amgen"), ("GILD", "Gilead"),
        ("REGN", "Regeneron"), ("VRTX", "Vertex"),
    ],
    "Medizintechnik & Gesundheit": [
        ("SHL.DE", "Siemens Healthineers"), ("FME.DE", "Fresenius Medical Care"), ("FRE.DE", "Fresenius"),
        ("SRT3.DE", "Sartorius Vz."), ("QIA.DE", "Qiagen"), ("GXI.DE", "Gerresheimer"),
        ("PHIA.AS", "Philips"), ("EL.PA", "EssilorLuxottica"), ("SN.L", "Smith & Nephew"), ("LONN.SW", "Lonza"),
        ("ABT", "Abbott"), ("MDT", "Medtronic"), ("SYK", "Stryker"), ("BSX", "Boston Scientific"),
        ("ISRG", "Intuitive Surgical"), ("TMO", "Thermo Fisher"), ("DHR", "Danaher"),
        ("UNH", "UnitedHealth"), ("ELV", "Elevance"), ("CI", "Cigna"), ("HUM", "Humana"), ("CVS", "CVS Health"),
    ],
    "Energie": [
        ("TTE.PA", "TotalEnergies"), ("SHEL.L", "Shell"), ("BP.L", "BP"), ("ENI.MI", "Eni"),
        ("REP.MC", "Repsol"), ("OMV.VI", "OMV"),
        ("XOM", "ExxonMobil"), ("CVX", "Chevron"), ("COP", "ConocoPhillips"), ("OXY", "Occidental"),
        ("EOG", "EOG Resources"), ("SLB", "SLB"), ("HAL", "Halliburton"),
        ("PSX", "Phillips 66"), ("VLO", "Valero"), ("MPC", "Marathon Petroleum"),
    ],
    "Versorger": [
        ("RWE.DE", "RWE"), ("EOAN.DE", "E.ON"), ("ENR.DE", "Siemens Energy"),
        ("ENEL.MI", "Enel"), ("IBE.MC", "Iberdrola"), ("ENGI.PA", "Engie"), ("VIE.PA", "Veolia"),
        ("NG.L", "National Grid"), ("SSE.L", "SSE"), ("EDP.LS", "EDP"),
        ("NEE", "NextEra"), ("DUK", "Duke Energy"), ("SO", "Southern Co"), ("D", "Dominion"),
        ("AEP", "AEP"), ("EXC", "Exelon"), ("XEL", "Xcel"),
    ],
    "Telekom": [
        ("DTE.DE", "Deutsche Telekom"), ("FNTN.DE", "Freenet"), ("1U1.DE", "1&1"), ("UTDI.DE", "United Internet"),
        ("ORA.PA", "Orange"), ("TEF.MC", "Telefónica"), ("VOD.L", "Vodafone"), ("BT-A.L", "BT Group"),
        ("KPN.AS", "KPN"),
        ("VZ", "Verizon"), ("T", "AT&T"), ("TMUS", "T-Mobile US"),
    ],
    "Konsumgüter (Staples)": [
        ("HEN3.DE", "Henkel Vz."), ("BEI.DE", "Beiersdorf"), ("SY1.DE", "Symrise"),
        ("NESN.SW", "Nestlé"), ("BN.PA", "Danone"), ("ULVR.L", "Unilever"), ("RKT.L", "Reckitt"),
        ("OR.PA", "L'Oréal"), ("GIVN.SW", "Givaudan"),
        ("KO", "Coca-Cola"), ("PEP", "PepsiCo"), ("PG", "Procter & Gamble"), ("CL", "Colgate-Palmolive"),
        ("KMB", "Kimberly-Clark"), ("MDLZ", "Mondelez"), ("GIS", "General Mills"), ("HSY", "Hershey"),
        ("KDP", "Keurig Dr Pepper"), ("MNST", "Monster Beverage"),
    ],
    "Getränke & Tabak": [
        ("ABI.BR", "AB InBev"), ("HEIA.AS", "Heineken"), ("DGE.L", "Diageo"), ("RI.PA", "Pernod Ricard"),
        ("CPR.MI", "Campari"), ("BATS.L", "BAT"), ("IMB.L", "Imperial Brands"),
        ("MO", "Altria"), ("PM", "Philip Morris"), ("STZ", "Constellation Brands"), ("TAP", "Molson Coors"),
    ],
    "Einzelhandel": [
        ("ZAL.DE", "Zalando"), ("ITX.MC", "Inditex"), ("AD.AS", "Ahold Delhaize"), ("CA.PA", "Carrefour"),
        ("TSCO.L", "Tesco"), ("JD.L", "JD Sports"), ("NXT.L", "Next"),
        ("WMT", "Walmart"), ("COST", "Costco"), ("TGT", "Target"), ("KR", "Kroger"),
        ("DG", "Dollar General"), ("DLTR", "Dollar Tree"), ("HD", "Home Depot"), ("LOW", "Lowe's"),
        ("TJX", "TJX"), ("ROST", "Ross Stores"), ("BBY", "Best Buy"), ("AMZN", "Amazon"),
    ],
    "Luxus & Sportartikel": [
        ("ADS.DE", "adidas"), ("PUM.DE", "Puma"), ("HUGO.DE", "Hugo Boss"),
        ("MC.PA", "LVMH"), ("RMS.PA", "Hermès"), ("KER.PA", "Kering"), ("CFR.SW", "Richemont"),
        ("BRBY.L", "Burberry"), ("MONC.MI", "Moncler"),
        ("NKE", "Nike"), ("RL", "Ralph Lauren"), ("TPR", "Tapestry"), ("LULU", "Lululemon"),
    ],
    "Gastronomie & Reise": [
        ("LHA.DE", "Lufthansa"), ("AF.PA", "Air France-KLM"), ("IAG.L", "IAG"), ("AC.PA", "Accor"),
        ("IHG.L", "IHG"), ("WTB.L", "Whitbread"),
        ("DAL", "Delta"), ("UAL", "United Airlines"), ("AAL", "American Airlines"), ("LUV", "Southwest"),
        ("MCD", "McDonald's"), ("SBUX", "Starbucks"), ("CMG", "Chipotle"), ("YUM", "Yum! Brands"),
        ("BKNG", "Booking"), ("MAR", "Marriott"), ("HLT", "Hilton"), ("RCL", "Royal Caribbean"), ("CCL", "Carnival"),
    ],
    "Industrie": [
        ("SIE.DE", "Siemens"), ("KBX.DE", "Knorr-Bremse"), ("KGX.DE", "Kion"), ("G1A.DE", "GEA Group"),
        ("ABBN.SW", "ABB"), ("SU.PA", "Schneider Electric"), ("LR.PA", "Legrand"),
        ("HON", "Honeywell"), ("GE", "GE Aerospace"), ("CAT", "Caterpillar"), ("DE", "Deere"),
        ("MMM", "3M"), ("EMR", "Emerson"), ("ETN", "Eaton"), ("ITW", "Illinois Tool Works"),
        ("PH", "Parker-Hannifin"), ("ROK", "Rockwell Automation"),
    ],
    "Rüstung & Luftfahrt": [
        ("RHM.DE", "Rheinmetall"), ("MTX.DE", "MTU Aero Engines"), ("HAG.DE", "Hensoldt"),
        ("AIR.PA", "Airbus"), ("SAF.PA", "Safran"), ("HO.PA", "Thales"), ("LDO.MI", "Leonardo"),
        ("BA.L", "BAE Systems"), ("RR.L", "Rolls-Royce"),
        ("LMT", "Lockheed Martin"), ("RTX", "RTX"), ("NOC", "Northrop Grumman"), ("GD", "General Dynamics"),
        ("BA", "Boeing"), ("LHX", "L3Harris"),
    ],
    "Transport & Logistik": [
        ("DHL.DE", "DHL Group"), ("HLAG.DE", "Hapag-Lloyd"), ("MAERSK-B.CO", "Maersk"), ("DSV.CO", "DSV"),
        ("KNIN.SW", "Kühne + Nagel"),
        ("UPS", "UPS"), ("FDX", "FedEx"), ("UNP", "Union Pacific"), ("CSX", "CSX"), ("NSC", "Norfolk Southern"),
        ("WM", "Waste Management"), ("RSG", "Republic Services"),
    ],
    "Bau & Baustoffe": [
        ("HEI.DE", "Heidelberg Materials"), ("HOT.DE", "Hochtief"),
        ("DG.PA", "Vinci"), ("SGO.PA", "Saint-Gobain"), ("ACS.MC", "ACS"), ("HOLN.SW", "Holcim"),
        ("CRH", "CRH"), ("VMC", "Vulcan Materials"), ("MLM", "Martin Marietta"),
        ("SHW", "Sherwin-Williams"), ("PPG", "PPG"),
    ],
    "Chemie": [
        ("BAS.DE", "BASF"), ("EVK.DE", "Evonik"), ("LXS.DE", "Lanxess"), ("WCH.DE", "Wacker Chemie"),
        ("SDF.DE", "K+S"), ("BNR.DE", "Brenntag"), ("FPE3.DE", "Fuchs Vz."),
        ("AI.PA", "Air Liquide"), ("AKZA.AS", "Akzo Nobel"), ("DSFIR.AS", "DSM-Firmenich"),
        ("LIN", "Linde"), ("APD", "Air Products"), ("ECL", "Ecolab"), ("DOW", "Dow"), ("DD", "DuPont"),
        ("LYB", "LyondellBasell"),
    ],
    "Rohstoffe & Bergbau": [
        ("RIO.L", "Rio Tinto"), ("GLEN.L", "Glencore"), ("AAL.L", "Anglo American"), ("ANTO.L", "Antofagasta"),
        ("NEM", "Newmont"), ("FCX", "Freeport-McMoRan"), ("NUE", "Nucor"), ("STLD", "Steel Dynamics"),
        ("AA", "Alcoa"), ("MT.AS", "ArcelorMittal"),
    ],
    "Immobilien": [
        ("VNA.DE", "Vonovia"), ("LEG.DE", "LEG Immobilien"), ("TEG.DE", "TAG Immobilien"), ("AT1.DE", "Aroundtown"),
        ("URW.PA", "Unibail-Rodamco"), ("LAND.L", "Land Securities"), ("BLND.L", "British Land"), ("SGRO.L", "Segro"),
        ("PLD", "Prologis"), ("AMT", "American Tower"), ("CCI", "Crown Castle"), ("EQIX", "Equinix"),
        ("SPG", "Simon Property"), ("O", "Realty Income"), ("PSA", "Public Storage"),
    ],
    "Halbleiter": [
        ("IFX.DE", "Infineon"), ("AIXA.DE", "Aixtron"), ("ASML.AS", "ASML"), ("ASM.AS", "ASM International"),
        ("BESI.AS", "BE Semiconductor"), ("STMPA.PA", "STMicroelectronics"),
        ("NVDA", "Nvidia"), ("AMD", "AMD"), ("INTC", "Intel"), ("AVGO", "Broadcom"), ("QCOM", "Qualcomm"),
        ("TXN", "Texas Instruments"), ("MU", "Micron"), ("AMAT", "Applied Materials"), ("LRCX", "Lam Research"),
        ("KLAC", "KLA"), ("ADI", "Analog Devices"), ("MRVL", "Marvell"), ("NXPI", "NXP"), ("ON", "onsemi"),
    ],
    "Software & IT-Dienste": [
        ("SAP.DE", "SAP"), ("NEM.DE", "Nemetschek"), ("BC8.DE", "Bechtle"), ("TMV.DE", "TeamViewer"),
        ("DSY.PA", "Dassault Systèmes"), ("CAP.PA", "Capgemini"), ("WKL.AS", "Wolters Kluwer"), ("SGE.L", "Sage"),
        ("MSFT", "Microsoft"), ("ORCL", "Oracle"), ("CRM", "Salesforce"), ("ADBE", "Adobe"), ("NOW", "ServiceNow"),
        ("INTU", "Intuit"), ("WDAY", "Workday"), ("IBM", "IBM"), ("ACN", "Accenture"), ("CSCO", "Cisco"),
        ("ADP", "ADP"), ("PAYX", "Paychex"), ("PANW", "Palo Alto Networks"), ("CRWD", "CrowdStrike"),
    ],
    "Internet & Medien": [
        ("PRX.AS", "Prosus"), ("PUB.PA", "Publicis"), ("WPP.L", "WPP"), ("REL.L", "RELX"),
        ("AAPL", "Apple"), ("GOOGL", "Alphabet"), ("META", "Meta"), ("NFLX", "Netflix"), ("UBER", "Uber"),
        ("DIS", "Disney"), ("CMCSA", "Comcast"), ("WBD", "Warner Bros. Discovery"), ("SPOT", "Spotify"),
        ("EBAY", "eBay"), ("ABNB", "Airbnb"),
    ],
}

def currency_of(ticker: str) -> str:
    if ticker.endswith(".SW"):
        return "CHF"
    if ticker.endswith(".L"):
        return "GBp"   # London notiert in Pence
    if ticker.endswith(".CO"):
        return "DKK"
    for suf in (".DE", ".PA", ".AS", ".MI", ".MC", ".BR", ".HE", ".VI", ".LS"):
        if ticker.endswith(suf):
            return "EUR"
    return "USD"


def region_of(ticker: str) -> str:
    if ticker.endswith(".DE"):
        return "DE"
    if "." in ticker:
        return "EU"
    return "US"


def all_tickers():
    seen, out = set(), []
    for sector, members in UNIVERSE.items():
        for t, name in members:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


# FX-Paare (Yahoo) zur Umrechnung in EUR: Preis_EUR = Preis_lokal / Kurs(EURXXX)
FX_TICKERS = {"USD": "EURUSD=X", "CHF": "EURCHF=X", "GBp": "EURGBP=X", "DKK": "EURDKK=X"}
