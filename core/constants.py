from pathlib import Path
from typing import Dict, List

# ficheiros históricos por modelo
MODEL_DATA_FILES: Dict[str, Path] = {
    "F5.2_20SEX": Path("tournament_results_F5.2.csv"),
    "M5.2_1830DOM": Path("tournament_results_M5.2.csv"),
    # adiciona aqui mais modelos/ficheiros no futuro
}

def get_data_file_for_model(model_id: str) -> Path:
    p = MODEL_DATA_FILES.get(model_id)
    return p if p is not None else Path("__no_data__.csv")


ALL_COURTS: List[str] = [
    "Campo Central",
    "Campo 11",
    "Campo 10",
    "Campo 9",
    "Campo 8",
    "Campo 7",
    "Campo 6",
    "Campo 5",
    "Campo 4",
    "Campo 3",
    "Campo 2",
    "Campo 1",
]

TOURNEY_TYPES = {
    "LIGA6": {
        "label": "Liga Clássica (6 Equipas)",
        "teams": 6,
        "groups": None,
        "required_courts": 3,
        "desc": "Todos contra todos; 5 jornadas; 3 jogos/jornada",
    },
    "G2x4": {
        "label": "Fase de Grupos: 2 Grupos de 4",
        "teams": 8,
        "groups": (2, 4),
        "required_courts": 4,
        "desc": "2 grupos; 3 jornadas; meias-finais cruzadas; total 5 jogos",
    },
    "G3x4": {
        "label": "Fase de Grupos: 3 Grupos de 4",
        "teams": 12,
        "groups": (3, 4),
        "required_courts": 6,
        "desc": "3 grupos; 3 jornadas; potes finais; total 5 jogos",
    },
    "G4x4": {
        "label": "Fase de Grupos: 4 Grupos de 4",
        "teams": 16,
        "groups": (4, 4),
        "required_courts": 8,
        "desc": "4 grupos; 3 jornadas; potes finais; total 5 jogos",
    },
    "UPDOWN": {
        "label": "Torneio Americano (Up & Down)",
        "teams": None,
        "groups": None,
        "required_courts": None,
        "desc": "Formato dinâmico por campos, com subidas/descidas",
    },
}

TOURNAMENTS = [
    {"id": "F5.2_20SEX", "nome": "PADEL4ALL EUL F5.2 / 6ª - Feira / 20h", "genero": "Feminino"},
    {"id": "M5.2_1830DOM", "nome": "PADEL4ALL EUL M5.2 / Dom / 18h30", "genero": "Masculino"},
    {"id": "M3.2_20DOM", "nome": "PADEL4ALL EUL M3.2 / Dom / 20h", "genero": "Masculino"},
]

POINTS_SYSTEM: Dict[int, List[int]] = {
    4:  [6, 4, 3, 2],
    6:  [8, 6, 4, 3, 2, 1],
    8:  [11, 9, 7, 6, 4, 3, 2, 1],
    10: [14, 12, 10, 9, 7, 6, 5, 4, 2, 1],
    12: [16, 14, 12, 11, 9, 8, 7, 6, 4, 3, 2, 1],
    14: [19, 17, 15, 14, 12, 11, 10, 9, 7, 6, 5, 4, 2, 1],
    16: [21, 19, 17, 16, 14, 13, 12, 11, 9, 8, 7, 6, 4, 3, 2, 1],
}

MONTH_ORDER = [
    "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
]
MONTH_INDEX = {m: i for i, m in enumerate(MONTH_ORDER)}

MONTH_ABBR_PT = ["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"]
