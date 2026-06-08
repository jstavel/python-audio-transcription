import time
import os
import sys
import argparse # Import argparse
from google import genai
from google.genai import types


# SDK si automaticky načte GEMINI_API_KEY z environment variables
client = genai.Client(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            initial_delay=1.0,      # Začne čekat 1 sekundu
            attempts=5,             # Zkusí to celkem 5x
            exp_base=2,             # Čas mezi pokusy se zdvojnásobí (1s, 2s, 4s, 8s, 16s)
            http_status_codes=[429, 500, 502, 503, 504]
        )
    )
)


# Kontextové volání modelu
prompt_template = """
Zpracuj připojený audio soubor. Tvým úkolem je vytvořit jeho doslovný
přepis a krátké shrnutí přímo ve formátu pro Emacs Org-mode. Striktně
dodržuj následující strukturu:

* Prepis {FILE_NAME}
:PROPERTIES:
:ID: [Zde vygeneruj jedinecne UUID]
:Path: {FILE_PATH}
:Source: Plaud
:Synopsis: [Zde napiš stručné shrnutí obsahu nahrávky jednou až dvěma větami – o čem nahrávka je, jaké je hlavní téma nebo klíčová myšlenka.]
:END:

#+begin_quote
[Zde bude doslovný přepis nahrávky slovo od slova. Vynechej pouze řečnickou výplň jako 'eee', 'vlastně', 'jakoby', 'prostě'.]
#+end_quote

Pravidla:
1. Vlastnost :Synopsis: napiš věcně a stručně, aby byla zachována přehlednost v org-mode.
2. Výstupem bude pouze čistý text v tomto formátu, bez jakýchkoliv tvých úvodních nebo závěrečných komentářů.
"""

def process_audio(file_path):
    print(f"Nahrávám soubor: {file_path}...")
    
    # 1. Upload přes File API
    audio_file = client.files.upload(file=file_path)
    
    # 2. Čekání na zpracování
    # U audia je klíčové počkat, až stav přejde z PROCESSING na ACTIVE
    while audio_file.state.name == "PROCESSING":
        print("Zpracovávám audio (čekám)...")
        time.sleep(2)
        audio_file = client.files.get(name=audio_file.name)
        
    if audio_file.state.name == "FAILED":
        raise ValueError(f"Chyba při zpracování: {audio_file.error.message}")

    print("Soubor je připraven, generuji odpověď...")
    file_name = os.path.basename(file_path)     
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            audio_file, # Předáváš nahraný soubor jako referenci
            prompt_template.format(
                FILE_NAME=file_name,
                FILE_PATH=file_path)
        ]
    )
    
    # 4. Úklid
    client.files.delete(name=audio_file.name)
    
    return response.text

# ---
# CONTEXT_FOR_AIDER
# - goal: transcribe.py understands an arg --input path of a file to transcribe
# - decisions: argparse is used
if __name__ == "__main__":
    # Create the parser
    parser = argparse.ArgumentParser(description="Transcribe an audio file using Google Gemini.")

    # Add the --input argument
    parser.add_argument("--input", type=str, required=True, help="Path to the audio file to transcribe.")

    # Parse the arguments
    args = parser.parse_args()

    # Use the input path from the arguments
    path = args.input
    
    # Preved cestu v promenne path na absolutni cestu
    absolute_path = os.path.expanduser(path)
    
    response = process_audio(absolute_path)

    # vypis promennou response do souboru s priponou .txt
    # Nazev souboru je odvozen z *absolute_path* = vymeni se pripona
    output_path = os.path.splitext(absolute_path)[0] + ".org"
    with open(output_path, "w") as f:
        f.write(str(response))
        
    print(f"vystup je ulozen v: {output_path}")
