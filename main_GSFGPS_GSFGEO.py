# Import the custom GPS serial communication class
from datetime import date
from time import sleep
import psycopg2
from PyGSFGPSSerial import *

# Contrôle de flux matériel (RTS/CTS) utilisé pendant la configuration.
# GSFGPS : RTS/CTS activé (comportement d'origine)
# GSFGEO : RTS/CTS désactivé pour la configuration initiale (ancienne ET nouvelle génération)
USING_BT_RTS_CTS_GPS = True
USING_BT_RTS_CTS_GEO = False


def connect_postgres() -> psycopg2.extensions.connection:
    """Établir la connexion à la base de données PostgreSQL."""

    try:
        conn = psycopg2.connect(
            host="192.168.1.168",
            port=5432,
            user="postgres",
            password="adminGSF",
            dbname="gsfclientslive"
        )

        # Vérifier la connexion
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()

        return conn

    except Exception as e:
        print(f"Échec de connexion à la base de données PostgreSQL: {str(e)}")
        raise


def add_device_to_db(device_name: str):
    today = date.today()
    formatted_date = today.strftime("%Y-%m-%d")

    try:
        conn = connect_postgres()
        cursor = conn.cursor()

        table = "inventaire"
        insert_query = f"""
            INSERT INTO {table} ("fournisseur", "etat", "pogsf", "facturefournisseur", "dateachat", "prixfournisseur", "item", "noserie")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        if device_name.split("-")[0] == "GSFGPS":
            product = "GSFGPS RV5"
        else:
            product = "GSFGEO"

        data_to_insert = ("GSF", "Stock", "GSF", "NA", formatted_date, 0.00, product, device_name)

        cursor.execute(insert_query, data_to_insert)
        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        conn.close()
        raise e


def get_last_id(device: str) -> str:
    """Obtenir le prochain ID disponible en interrogeant la table inventaire."""
    last_id = ""

    try:
        conn = connect_postgres()
        cursor = conn.cursor()

        if device == "GSFGPS":
            query = "SELECT \"noserie\" FROM \"inventaire\" WHERE \"noserie\" LIKE 'GSFGPS-%'"
            default_id = "GSFGPS-5000"
            prefix = "GSFGPS"
        elif device == "GSFGEO":
            query = "SELECT \"noserie\" FROM \"inventaire\" WHERE \"noserie\" LIKE 'GSFGEO-%'"
            default_id = "GSFGEO-25000"
            prefix = "GSFGEO"
        else:
            return ""

        cursor.execute(query)
        results = cursor.fetchall()

        if results:
            max_num = 0
            for row in results:
                serial = row[0]
                if serial:
                    parts = serial.split('-')
                    if len(parts) == 2:
                        try:
                            num = int(parts[1])
                            if num > max_num:
                                max_num = num
                        except ValueError:
                            continue

            if max_num > 0:
                print(f"Dernier Numéro de série: {max_num}")
                next_num = max_num + 1
                last_id = f"{prefix}-{next_num}"
                print(f"Prochain numéro de série disponible: {last_id}")
            else:
                print(f"Aucune entrée {prefix} valide trouvée, démarrage à {default_id}")
                last_id = default_id
        else:
            print(f"Aucune entrée {prefix} existante trouvée, démarrage à {default_id}")
            last_id = default_id

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Erreur lors de l'interrogation de la base de données: {e}")
        if device == "GSFGPS":
            last_id = "GSFGPS-5000"
        elif device == "GSFGEO":
            last_id = "GSFGEO-25000"

    return last_id


def ask_bluetooth_name(device: str) -> str:
    """Proposer le prochain numéro de série et laisser l'utilisateur le modifier."""
    print("\nRécupération du prochain numéro de série disponible...")
    sleep(1)
    bluetooth_name = get_last_id(device)

    user_input = input("\nAppuyez sur Entrée pour accepter ou entrez un autre nom: ").strip()
    if user_input:
        bluetooth_name = user_input

    return bluetooth_name


def ask_yes_no(question: str) -> bool:
    """Poser une question oui/non (o/n)."""
    return input(question).strip().lower() in ("o", "oui", "y", "yes")


def main():
    # Obtenir le port COM de l'utilisateur
    com_port = input("Entrez le port COM (ex: COM6): ").strip()

    # Le type d'appareil est demandé avant l'ouverture du port,
    # car le contrôle de flux RTS/CTS en dépend.
    device_type = input("\nEntrez le type de GPS (GSFGPS : 1, GSFGEO : 2): ").strip()

    is_geo = False
    is_geo_new_generation = False

    if device_type == "1":
        device = "GSFGPS"
        use_rtscts = USING_BT_RTS_CTS_GPS
    elif device_type == "2":
        device = "GSFGEO"
        is_geo = True
        use_rtscts = USING_BT_RTS_CTS_GEO
        is_geo_new_generation = ask_yes_no("Est-ce un GSFGEO nouvelle génération? (o/n): ")
    else:
        print("ERREUR: Type de dispositif invalide")
        return

    # Initialiser le module GPS avec le port spécifié par l'utilisateur
    gps = PyGSFGPSSerial(port=com_port, rtscts=use_rtscts)

    # Tenter d'établir la connexion série
    print(f"\nTentative de connexion à {com_port}...")
    sleep(1)
    if not gps.open():
        print(f"ERREUR: Impossible d'ouvrir la connexion sur {com_port}")
        print("Veuillez vérifier:")
        print("  - Le port COM existe et est correct")
        print("  - L'appareil est correctement connecté")
        print("  - Aucune autre application n'utilise ce port")
        return

    print(f"SUCCÈS: Connecté à {com_port}")

    bluetooth_name = ask_bluetooth_name(device)

    if not bluetooth_name:
        print("ERREUR: Le nom Bluetooth ne peut pas être vide")
        gps.close()
        return

    print(f"\nConfiguration du module Bluetooth avec le nom: {bluetooth_name}")
    sleep(2)
    try:
        gps.set_dtr(True)

        print("\nPassage en mode commande...")
        gps.enter_command_mode()

        print("Test du mode commande...")
        gps.send_at_command("AT")

        print("Configuration du mode Data par défaut au démarrage...")
        gps.send_at_command("AT+UMSM={}".format(1))

        print("Vérification du mode de démarrage...")
        gps.send_at_command("AT+UMSM?")

        print(f"Configuration du nom Bluetooth: {bluetooth_name}")
        gps.send_at_command("AT+UBTLN={}".format(bluetooth_name))

        print("Vérification du nom Bluetooth...")
        gps.send_at_command("AT+UBTLN?")

        if is_geo:
            print("Test de vérification avant la suite de la configuration...")
            gps.send_at_command("AT")

            if is_geo_new_generation:
                # Module Bluetooth à 115200 bauds, SANS contrôle de flux.
                # 2e paramètre : contrôle de flux 1=CTS/RTS (défaut), 2=Aucun
                # Dernier paramètre : 0=appliquer au prochain redémarrage, 1=immédiatement
                print("Configuration du Bluetooth à 115200 bauds, sans contrôle de flux (GSFGEO nouvelle génération)...")
                gps.send_at_command("AT+UMRS={}".format("115200,2,8,1,1,0"))

                print("Vérification de la configuration série...")
                gps.send_at_command("AT+UMRS?")

        print("Enregistrement de la configuration...")
        gps.send_at_command("AT&W0")

        print("Redémarrage du module pour sauvegarder les paramètres...")
        gps.send_at_command("AT+CPWROFF")

        print("Test final du mode commande...")
        gps.send_at_command("AT")

        print("Passage en mode Data...")
        gps.enter_data_mode()

        gps.set_dtr(False)

        print("\n" + "=" * 50)
        print("Configuration terminée avec succès!")
        print(f"Module configuré avec le nom: {bluetooth_name}")
        add_device_to_db(bluetooth_name)
        print("=" * 50)

    except Exception as e:
        print(f"\nERREUR pendant la configuration: {e}")
    finally:
        gps.close()
        print("Connexion série fermée.")
        print("=" * 50)


if __name__ == "__main__":
    main()
