import imaplib
import smtplib
import email
import time
import os
import requests


from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

MAIL = os.getenv("MAIL")
HASLO = os.getenv("HASLO")
GROQ_KEY = os.getenv("GROQ_KEY")

URL_KLIENTA = os.getenv("URL_KLIENTA", "https://mala-toscania.eatbu.com/?lang=pl")
NAZWA_FIRMY = os.getenv("NAZWA_FIRMY", "Firma")

def pobierz_informacje_ze_strony(url):
    try:
        odpowiedz = requests.get(url, timeout=10)
        soup = BeautifulSoup(odpowiedz.text, "html.parser")
        for zbedny in soup(["script", "style", "nav", "footer", "header"]):
            zbedny.decompose()
        tekst = soup.get_text(separator="\n")
        linie = [l.strip() for l in tekst.splitlines() if l.strip()]
        return "\n".join(linie[:200])
    except Exception as e:
        print(f"Błąd pobierania strony: {e}")
        return "Brak informacji o firmie"

informacje_o_restauracji = pobierz_informacje_ze_strony(URL_KLIENTA)
print("Pobrano informacje ze strony klienta")

def czytaj_maile():
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(MAIL, HASLO)
    imap.select("inbox")
    _, wiadomosci = imap.search(None, "UNSEEN")
    maile = []
    for num in wiadomosci[0].split():
        _, dane = imap.fetch(num, "(RFC822)")
        wiadomosc = email.message_from_bytes(dane[0][1])
        nadawca = wiadomosc["From"]
        temat = wiadomosc["Subject"]
        if wiadomosc.is_multipart():
            tresc = ""
            for part in wiadomosc.walk():
                if part.get_content_type() == "text/plain":
                    tresc = part.get_payload(decode=True).decode()
        else:
            tresc = wiadomosc.get_payload(decode=True).decode()
        maile.append({"nadawca": nadawca, "temat": temat, "tresc": tresc})
    imap.close()
    return maile

def generuj_odpowiedz(tresc_maila):
    client = Groq(api_key=GROQ_KEY)
    odpowiedz = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": f"Jesteś asystentem restauracji Mała Toscania. Odpowiadasz krótko i uprzejmie na podstawie:\n{informacje_o_restauracji}\nJeśli nie znasz odpowiedzi — odsyłaj do telefonu 604546087. Jeśli ktoś jest nieprzyjemny lub używa wulgarnych słów — grzecznie odpowiedz że chętnie pomożesz gdy będzie rozmawiał kulturalnie."},
            {"role": "user", "content": tresc_maila}
        ]
    )
    return odpowiedz.choices[0].message.content

def wyslij_odpowiedz(do, temat, tresc):
    smtp = smtplib.SMTP("smtp-relay.brevo.com", 587)
    smtp.starttls()
    smtp.login(os.getenv("BREVO_LOGIN"), os.getenv("BREVO_HASLO"))
    wiadomosc = MIMEText(tresc)
    wiadomosc["From"] = MAIL
    wiadomosc["To"] = do
    wiadomosc["Subject"] = "Re: " + temat
    smtp.send_message(wiadomosc)
    smtp.quit()
    print(f"Wysłano odpowiedź do: {do}")
    
while True:
    print("Sprawdzam maile...")
    maile = czytaj_maile()
    if not maile:
        print("Brak nowych maili")
    else:
        for mail in maile:
            print(f"Nowy mail od: {mail['nadawca']}")
            odpowiedz = generuj_odpowiedz(mail["tresc"])
            print(f"Odpowiedź: {odpowiedz}")
            wyslij_odpowiedz(mail["nadawca"], mail["temat"], odpowiedz)
    print("Czekam 5 minut...")
    time.sleep(300)
