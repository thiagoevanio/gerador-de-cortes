"""Associação audiovisual local com abstenção, sem download de modelos ou credenciais."""
import numpy as np


def vetores_voz(audio,tempos,frequencia=16000):
    linhas=[]
    bandas=np.geomspace(80,6000,18)
    frequencias=np.fft.rfftfreq(1024,1/frequencia)
    dct=np.cos(np.pi/17*(np.arange(17)+.5)[None,:]*np.arange(1,9)[:,None])
    for t in tempos:
        a=max(0,int((t-.3)*frequencia));b=min(len(audio),int((t+.3)*frequencia))
        trecho=audio[a:b]
        if len(trecho)<1024 or np.sqrt(np.mean(trecho**2))<.003:
            linhas.append(None);continue
        frames=np.stack([trecho[i:i+1024] for i in range(0,len(trecho)-1023,512)])
        espectro=(np.abs(np.fft.rfft(frames*np.hanning(1024),axis=1))**2).mean(axis=0)
        energias=np.array([espectro[(frequencias>=x)&(frequencias<y)].mean() for x,y in zip(bandas,bandas[1:])])
        cepstro=dct@np.log(energias+1e-10)
        cepstro=cepstro/(np.linalg.norm(cepstro)+1e-8)
        linhas.append(cepstro)
    return linhas


def associar(vetores,mov_a,mov_b,mascara_fala,minimo_suporte=5):
    validos=[i for i,v in enumerate(vetores) if v is not None and mascara_fala[i]]
    desconhecidos=[None]*len(vetores)
    if len(validos)<minimo_suporte*2:return desconhecidos,dict(metodo='audiovisual_local',confiavel=False,motivo='Pouca fala comparável.')
    x=np.array([vetores[i] for i in validos])
    c0=x[0];c1=x[np.argmax(np.linalg.norm(x-c0,axis=1))]
    centros=np.stack([c0,c1])
    for _ in range(30):
        dist=np.linalg.norm(x[:,None,:]-centros[None,:,:],axis=2)
        grupos=dist.argmin(axis=1)
        if len(set(grupos))<2:return desconhecidos,dict(confiavel=False,motivo='Apenas um grupo acústico identificável.')
        novos=np.stack([x[grupos==g].mean(axis=0) for g in range(2)])
        if np.max(np.abs(novos-centros))<1e-5:break
        centros=novos
    dispersao=np.mean(np.linalg.norm(x-centros[grupos],axis=1))+1e-6
    separacao=float(np.linalg.norm(centros[0]-centros[1])/dispersao)
    mapas={};suportes={}
    for g in range(2):
        votos={'A':0.,'B':0.}
        for j,i in enumerate(validos):
            if grupos[j]!=g:continue
            a,b=float(mov_a[i]),float(mov_b[i])
            if max(a,b)<1 or max(a,b)<1.6*max(.01,min(a,b)):continue
            votos['A' if a>b else 'B']+=1
        vencedor=max(votos,key=votos.get)
        total=sum(votos.values())
        if total>=minimo_suporte and votos[vencedor]/total>=.75:
            mapas[g]=vencedor;suportes[g]=int(total)
    confiavel=len(mapas)==2 and len(set(mapas.values()))==2 and separacao>=1.35
    rel=dict(metodo='audiovisual_local',confiavel=confiavel,separacao=round(separacao,3),suportes=suportes,
             motivo='Voz e movimento visual associados.' if confiavel else 'Associação inconclusiva; não atribuir falante.')
    if not confiavel:return desconhecidos,rel
    for j,i in enumerate(validos):
        d=np.linalg.norm(centros-vetores[i],axis=1)
        g=int(np.argmin(d));margem=(max(d)-min(d))/max(1e-6,max(d))
        # Contradição visual forte invalida uma atribuição acústica.
        pessoa=mapas[g]
        contrario=mov_b[i]>mov_a[i]*1.8 if pessoa=='A' else mov_a[i]>mov_b[i]*1.8
        if margem>=.25 and not contrario:desconhecidos[i]=pessoa
    return desconhecidos,rel
