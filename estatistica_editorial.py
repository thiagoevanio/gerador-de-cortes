"""Comparações conservadoras de amostras equivalentes, com incerteza explícita."""
import random
import statistics


def contraste(a,b,minimo=8):
    if len(a)<minimo or len(b)<minimo:return dict(conclusivo=False,motivo='Amostra insuficiente por grupo.')
    rng=random.Random(9173)
    diferencas=[]
    for _ in range(1000):
        diferencas.append(statistics.median(rng.choices(a,k=len(a)))-statistics.median(rng.choices(b,k=len(b))))
    diferencas.sort()
    inferior,superior=diferencas[25],diferencas[974]
    return dict(conclusivo=inferior>0 or superior<0,intervalo_diferenca_95=[inferior,superior],
                amostras=[len(a),len(b)],metodo='bootstrap de medianas; associação observacional')
