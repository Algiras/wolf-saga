#!/usr/bin/env python3
"""
Download character voice references from ElevenLabs API.
Generates a unique sample for each character to use as a TTS reference.
"""

import os
import requests
import json
from pathlib import Path

# Load env file manually since we don't have python-dotenv installed in this env potentially
def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

load_env()

API_KEY = os.environ.get("ELEVEN_LABS_API") or os.environ.get("ELEVENLABS_API_KEY")

if not API_KEY:
    print("❌ Error: ELEVEN_LABS_API key not found in .env")
    exit(1)

VOICE_DIR = Path(__file__).parent / "voices"
VOICE_DIR.mkdir(exist_ok=True)

# Mapping of Characters to ElevenLabs Voice IDs and Sample Text
# Using standard pre-made voices with 30-second narrative samples
CHARACTERS = {
    "narrator": {
        "voice_id": "pNInz6obpgDQGcFmaJgB", # Adam (Dominant, Firm)
        "text": "In the shadowed depths of ancient Lithuania, where the amber forests whispered secrets to the wind, a great storm was gathering. The year was 1385, and the Grand Duchy stood at a crossroads between pagan tradition and Christian conversion. Kestutis, the mighty warrior duke, defended the old ways with unyielding resolve, while his nephew Jogaila, the ambitious young ruler, saw opportunity in alliance with Poland. But beneath the surface of political maneuvering, darker forces stirred - immortal beings who had walked the earth since the dawn of time, manipulating the fates of men for their own mysterious purposes."
    },
    "kestutis": {
        "voice_id": "JBFqnCBsd6RMkjVDRZzb", # George (Warm, Captivating Storyteller)
        "text": "Listen well, my people. For generations, our ancestors have defended these sacred lands against invaders from east and west. The Teutonic Knights come with their crosses and their steel, claiming to bring salvation, but they bring only death and slavery. Our gods - Perkunas the thunderer, Zemyna the earth mother - they have sustained us through famine and war. I, Kestutis, son of Gediminas, will not abandon the ways of our fathers. The iron of our will is stronger than any foreign steel. We will fight, we will bleed, but we will never surrender our freedom. The forests and rivers of Lithuania will run red with enemy blood before we bend our knees to outsiders."
    },
    "vytautas": {
        "voice_id": "TX3LPaxmHKxFdv7VOQHJ", # Liam (Energetic, Social Media Creator)
        "text": "The future belongs to those bold enough to seize it! While my uncle Kestutis clings to the past, I see the winds of change blowing across Europe. The Lithuanian tribes must unite, not just in name but in purpose. We have the greatest cavalry in Christendom, warriors who can outride and outfight any army. But we need allies, we need trade, we need the knowledge of the West. I will not be bound by the superstitions of yesterday. The future is not written in stone, but forged in the fires of our ambition. With me as your leader, Lithuania will become an empire that stretches from the Baltic to the Black Sea, feared and respected by all nations."
    },
    "jogaila": {
        "voice_id": "cjVigY5qzO86Huf0OWal", # Eric (Smooth, Trustworthy)
        "text": "Power is not taken by force alone, cousin Vytautas. It requires calculation, patience, and the ability to see ten moves ahead on the chessboard of politics. The world is changing around us - the Teutonic Order grows stronger each day, Poland seeks allies against the growing Ottoman threat, and Moscow eyes our eastern territories. I have watched the great rulers of history: Alexander, Caesar, Charlemagne. They understood that empires are built not just on swords, but on alliances and marriages. The pagan ways served our ancestors well, but now we must adapt or be swept away by the tide. Baptism, marriage to Jadwiga of Poland - these are not acts of surrender, but strategic maneuvers that will secure our legacy for centuries to come."
    },
    "skirgaila": {
        "voice_id": "SOYHLrjzK2X1ezoPC6cr", # Harry (Fierce Warrior)
        "text": "Enough of this endless talking! My blade grows restless in its scabbard. The enemy approaches our borders, and you sit here debating theology and politics? I am Skirgaila, son of Kestutis, and I was born for battle. My horse Thunder knows the scent of blood as well as I do. We have crushed the Golden Horde at the Battle of Blue Waters, sent the Teutons fleeing back to their castles. My patience wears thin with these endless councils and diplomatic games. If you want to talk peace, talk to my sword. It speaks a language everyone understands. The next man who questions my courage will find steel in his gut before he finishes his sentence. We fight, or we die - there is no middle ground for warriors like me."
    },
    "envoy": {
        "voice_id": "iP95p4xoKVk53GoZ742B", # Chris (Charming, Down-to-Earth)
        "text": "My lords, I come bearing greetings from His Majesty King Wenceslaus of Bohemia and the Holy Roman Emperor. The courts of Europe watch your struggle with great interest. The Teutonic Order claims you are savage pagans who reject civilization, but I have seen your cities, your scholars, your warriors. You are no barbarians. The Pope in Rome understands that Lithuania could be a powerful ally against the Ottoman Turks who threaten Constantinople itself. I bring word from the west - the Order marches at dawn, but they march without the blessing of the Church. Join us in Christendom, and you will find not masters, but brothers. Your amber, your furs, your strategic position - these could make you wealthy beyond imagining. But the choice is yours. Will you stand alone against the storm, or join the family of Christian nations?"
    },
    "velnias": { # Devil / Shadow-Seller
        "voice_id": "N2lVS1w4EtoT3dr4eOWO", # Callum (Husky Trickster)
        "text": "Ah, mortal souls, always so predictable in their desperation. You come to me in the dead of night, whispering your secrets, begging for power that you cannot earn through your own meager efforts. I am Velnias, the Shadow-Seller, the Devil of the Crossroads. For centuries I have wandered these lands, offering deals to kings and peasants alike. Want victory in battle? A crown? The love of a woman who scorns you? Everything has its price. The shadows have a price, mortal. Are you willing to pay it? Your firstborn child? Your immortal soul? Your very humanity? The choice is yours, but choose wisely. Once the bargain is struck, there is no turning back. The darkness hungers, and I am merely its servant."
    },
    "zemyna": { # Amber Queen / Birute
        "voice_id": "EXAVITQu4vr4xnSDxMaL", # Sarah (Mature, Reassuring, Confident)
        "text": "Peace, my children. The earth remembers every footstep, every drop of blood spilled upon her sacred soil. I am Zemyna, Queen of the Amber, guardian of the ancient groves where the old gods still walk among the trees. For a thousand years, my priestesses have tended the sacred fires, read the patterns in the amber stones that hold the tears of the sun. The Christians call me a pagan idol, but I am the living spirit of this land. The rivers carry my blessings, the forests shelter my children. Even as Jogaila considers baptism, I know the old ways cannot die so easily. The earth endures, the cycles continue. Trust in the natural order, my beloved ones. The amber holds the tears of the sun, and those tears will heal all wounds in time."
    },
    "perkunas": {
        "voice_id": "pqHfZKP75CvOlQylNhV4", # Bill (Wise, Mature, Balanced)
        "text": "Hear me, you insignificant mortals! I am Perkunas, Lord of Thunder, Rider of the Storm, the great god who forged the heavens with my mighty hammer! For eons I have watched your petty squabbles, your wars and your peaces, your births and your deaths. The skies tremble at my approach, lightning splits the darkness, and rain nourishes the earth that is my wife's domain. You pray to your foreign god on his cross, but when the storms rage and the crops fail, it is to me you turn. Let the thunder roll and the skies tear asunder! I am the storm incarnate, the wrath of the heavens made flesh. Bow before me, or face my fury. The oak trees bend in my presence, the wolves howl my name. I am eternal, unchanging, the force that shaped this world before your ancestors crawled from the mud."
    },
    "medeine": { # Egle / Vaidilute
        "voice_id": "FGY2WhTYpPnrIDTdsKH5", # Laura (Enthusiast, Quirky Attitude)
        "text": "Oh, the forest is alive tonight! Can't you feel it? The trees are whispering secrets to each other, the wind carries messages from the spirits of the air. I am Medeine, daughter of the forest, protector of all wild things. My sisters and I dance beneath the full moon, our bare feet kissing the sacred earth. The Christians call us witches and demons, but we are the keepers of the old magic, the healers who know every herb and root. The forest whispers to those who listen. The spirits are restless tonight - they sense the coming changes, the clash between the old ways and the new. But magic cannot be contained by churches or crowns. It flows through the rivers, it sings in the wind, it lives in the heart of every true Lithuanian. Come, join our circle! The night is young, and the spirits are calling."
    }
}

# Also need to ensure output filenames match what 2_generate_audio.py expects
# 2_generate_audio.py expects:
# reference_voice.wav (Narrator)
# kestutis.wav
# vytautas.wav
# jogaila.wav
# skirgaila.wav
# envoy.wav
# velnias.wav
# zemyna.wav
# perkunas.wav
# medeine.wav

FILENAME_MAP = {
    "narrator": "reference_voice.wav",
    "kestutis": "kestutis.wav",
    "vytautas": "vytautas.wav",
    "jogaila": "jogaila.wav",
    "skirgaila": "skirgaila.wav",
    "envoy": "envoy.wav",
    "velnias": "velnias.wav",
    "zemyna": "zemyna.wav",
    "perkunas": "perkunas.wav",
    "medeine": "medeine.wav"
}

def download_voice(name, data):
    filename = FILENAME_MAP.get(name, f"{name}.wav")
    output_path = VOICE_DIR / filename
    
    # Optional: Backup existing
    # if output_path.exists():
    #     print(f"⚠️  Overwriting existing {filename}...")
    
    voice_id = data["voice_id"]
    text = data["text"]
    
    print(f"🎙️  Generating {name} ({voice_id})...")
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            # Save as wav (response is mpeg, but we can save as wav or convert)
            # Chatterbox might want wav. Let's save as mp3 first then use ffmpeg to convert to strict wav
            
            temp_mp3 = VOICE_DIR / f"{name}_temp.mp3"
            with open(temp_mp3, "wb") as f:
                f.write(response.content)
            
            # Convert to WAV 24kHz mono using ffmpeg
            import subprocess
            cmd = [
                "ffmpeg", "-y", "-i", str(temp_mp3),
                "-ar", "24000", "-ac", "1",
                str(output_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Remove temp
            temp_mp3.unlink()
            
            print(f"   ✅ Saved to {filename}")
        else:
            print(f"   ❌ API Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Failed: {e}")

def main():
    print(f"🚀 Starting ElevenLabs voice generation for {len(CHARACTERS)} characters...")
    print(f"📂 Output directory: {VOICE_DIR}")
    
    for name, data in CHARACTERS.items():
        download_voice(name, data)
        
    print("\n✨ All voices generated!")

if __name__ == "__main__":
    main()
