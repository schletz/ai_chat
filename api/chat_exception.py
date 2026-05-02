# Eigene Exception-Klasse. Anstatt generische Exceptions zu werfen,
# erstellen wir fachspezifische (domain-specific) Fehlermeldungen.
# Dadurch können aufrufende Schichten diese gezielt abfangen (Try-Catch) und behandeln.
class ChatException(Exception):
    pass
