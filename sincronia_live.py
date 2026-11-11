"""Alinhamento temporal e confirmação de conteúdo por hash perceptual de quadros."""
import math
import re
import subprocess


def posicao(duracao, atraso_player=0, atraso_captura=0, ajuste=0, capturado_em=None, agora=None):
    valores=[duracao,atraso_player,atraso_captura,ajuste]
    if not all(math.isfinite(float(x)) for x in valores) or not 0<=atraso_player<=180 or abs(ajuste)>60:
        raise ValueError('Sincronização inválida; volte o player para perto do ao vivo.')
    transporte=0
    if capturado_em is not None and agora is not None:
        transporte=agora-capturado_em
        if not math.isfinite(transporte) or not -5<=transporte<=180:
            raise ValueError('Marcação expirada; sincronize a extensão novamente.')
        transporte=max(0,transporte)
    return max(0,duracao+atraso_captura-atraso_player-transporte+ajuste)


def dhash(pixels):
    if len(pixels)!=72:raise ValueError('Quadro deve conter 9×8 pixels.')
    n=0
    for y in range(8):
        for x in range(8):n=(n<<1)|int(pixels[y*9+x]>pixels[y*9+x+1])
    return n


def escolher(amostras, alvo, previsto, limiar=10):
    if not re.fullmatch('[0-9a-fA-F]{16}',alvo or ''):return dict(confirmado=False,motivo='Quadro do player indisponível.')
    numero=int(alvo,16)
    ranking=sorted(((numero^h).bit_count(),t) for t,h in amostras)
    if len(ranking)<3:return dict(confirmado=False,motivo='Poucos quadros comparáveis na gravação.')
    distancia,t=ranking[0]
    concorrentes=[d for d,tt in ranking[1:] if abs(tt-t)>3]
    margem=min(concorrentes)-distancia if concorrentes else 0
    ok=distancia<=limiar and margem>=3
    return dict(confirmado=ok,instante=t if ok else previsto,distancia=distancia,margem=margem,
                motivo='Conteúdo do player localizado na gravação.' if ok else 'Imagem ambígua ou diferente; mantida a estimativa temporal.')


def alinhar(fonte,previsto,alvo,janela=16):
    if not re.fullmatch('[0-9a-fA-F]{16}',alvo or ''):return escolher([],alvo,previsto)
    import cortes
    cortes.checar_ffmpeg()
    a=max(0,previsto-janela)
    dur=cortes.duracao_video(fonte)
    b=min(dur,previsto+janela)
    if b<=a:return dict(confirmado=False,motivo='Posição fora da gravação.')
    r=subprocess.run(['ffmpeg','-v','error','-threads','2','-ss',str(a),'-i',str(fonte),'-t',str(b-a),
                      '-vf','fps=1,scale=9:8:flags=area,format=gray','-f','rawvideo','-'],capture_output=True,
                      timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if r.returncode:return dict(confirmado=False,motivo='Não foi possível confirmar o quadro.')
    return escolher([(a+i,dhash(r.stdout[i*72:(i+1)*72])) for i in range(len(r.stdout)//72)],alvo,previsto)
