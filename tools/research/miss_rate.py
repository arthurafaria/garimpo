"""Mede quantas respostas plausíveis faltam no pool atual (regras de src/game/match.ts)."""
import json, sys, unicodedata, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
STOP = {"de","da","do","das","dos","e","o","a","os","as","um","uma"}
def norm(v):
    v = unicodedata.normalize("NFD", v); v = "".join(c for c in v if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",v.lower()).strip())
def key(v): return " ".join(t for t in norm(v).split(" ") if t and t not in STOP)
def st(t):
    if len(t)<=3 or t.isdigit(): return t
    for a,b in (("oes","ao"),("aes","ao"),("eis","el"),("ais","al")):
        if t.endswith(a): return t[:-3]+b
    if t.endswith("ns"): return t[:-2]+"m"
    if t.endswith(("res","zes","ses")): return t[:-2]
    if t.endswith("s") and not t.endswith("ss"): return t[:-1]
    return t
def stem(v): return " ".join(st(t) for t in key(v).split(" ") if t)
def forms(v):
    n=norm(v); k=key(v) or n; s=stem(v) or k
    return {n,k,s,k.replace(" ",""),s.replace(" ","")}
def lev(a,b,cap):
    if abs(len(a)-len(b))>cap: return cap+1
    prev=list(range(len(b)+1)); before=None
    for i in range(1,len(a)+1):
        row=[i]
        for j in range(1,len(b)+1):
            v=min(prev[j]+1,row[j-1]+1,prev[j-1]+(a[i-1]!=b[j-1]))
            if i>1 and j>1 and a[i-1]==b[j-2] and a[i-2]==b[j-1]: v=min(v,before[j-2]+1)
            row.append(v)
        before,prev=prev,row
    return prev[-1]
def budget(n): return 0 if n<=3 else 1 if n<=5 else 2 if n<=10 else 3
TIER = sys.argv[1] if len(sys.argv)>1 else "1"
TESTS2 = {
 "bebida-todas": ["Guaravita","Itubaína","Toddynho","chá mate","Matte Leão","açaí","garapa","cachaça 51","Ypióca","Catuaba","Corote","Skol","suco de maracujá","vitamina de abacate","café com leite"],
 "refrigerante-br": ["Guaraná Antártica","Guaravita","Antarctica","Guaraná Kuat","Funada","Xereta","Taí","Frisante","Guaraná Fys","Teem","H2OH","Schin","Guaraná Schin","Mate Couro","São Geraldo"],
 "doce-todos": ["arroz doce","bala de coco","maria mole","bolo de cenoura","mousse de maracujá","pavê","sagu","ambrosia","olho de sogra","rapadura","doce de abóbora","brownie","pé de moça","mungunzá","churros"],
 "prato-nordeste": ["baião de dois","acarajé","tapioca","cuscuz","buchada","carne de sol","sarapatel","moqueca","vatapá","escondidinho","cuscuz com ovo","macaxeira","arrumadinho","rubacão","feijão verde"],
 "marca-todas": ["Toddy","Nescau","Bauducco","Trakinas","Club Social","Passatempo","Negresco","Garoto","Lacta","Sazón","Maggi","Omo","Bombril","Kibon","Itambé"],
 "giria-todas": ["cringe","tankar","de rocha","pistola","gado","biscoiteiro","mitou","lacrou","flopou","shippar","mozão","bora","oxe","partiu","hater"],
 "cantor-todos": ["Gil","Milton","Djavan","Simone Mendes","Henrique e Juliano","Matuê","Liniker","Alok","MC Kevinho","Wesley Safadão","Leonardo","Joelma","Pablo","Tierry","Zezé"],
 "cantor-funk": ["Anitta","Ludmilla","MC Kevin o Chris","Kevin O Chris","MC Livinho","MC Hariel","MC Ryan SP","Dennis DJ","Furacão 2000","Bonde do Tigrão","MC Marcinho","Valesca Popozuda","MC Poze do Rodo","Pocah","MC Carol"],
}
TESTS = {
 "bebida-todas": ["cachaça","caipirinha","guaraná","Kuat","café","cafezinho","chimarrão","tereré","caldo de cana","mate","suco de caju","cerveja","Guaraná Jesus","quentão","batida"],
 "refrigerante-br": ["Guaraná Antarctica","Kuat","Fanta","Guaraná Jesus","Dolly","Itubaína","Tubaína","Mineirinho","Convenção","Pakera","Cotuba","Guaraná Charrua","Coca-Cola","Sukita","Soda Limonada"],
 "doce-todos": ["brigadeiro","beijinho","doce de leite","pé de moleque","paçoca","quindim","cocada","goiabada","romeu e julieta","pudim","bolo de rolo","canjica","cajuzinho","bombom","sonho"],
 "salgado-festa": ["coxinha","kibe","quibe","risole","rissole","enroladinho de salsicha","esfiha","empadinha","bolinha de queijo","pastel","croquete","mini pizza","pão de queijo","cigarrete","joelho"],
 "petisco-boteco": ["batata frita","torresmo","bolinho de bacalhau","calabresa acebolada","frango a passarinho","pastel","isca de peixe","caldinho de feijão","mandioca frita","aipim frito","amendoim","ovo colorido","pururuca","linguiça","porção de frios"],
 "marca-todas": ["Havaianas","Natura","Boticário","Bombril","Nescau","Toddy","Kuat","Piraquê","Tramontina","Sadia","Perdigão","Ypê","Melissa","Brahma","Guaraná Antarctica"],
 "giria-todas": ["mano","véi","top","massa","bagulho","rolê","crush","mó","de boa","zoeira","sextou","tá ligado","parça","treta","mina"],
 "cantor-todos": ["Anitta","Ivete","Roberto Carlos","Caetano","Gil","Marília Mendonça","Gusttavo Lima","Luan Santana","Ludmilla","Xuxa","Pabllo Vittar","Zé Felipe","MC Daleste","Jorge e Mateus","Belo"],
}
d=json.load(open(ROOT/"public/data/garimpo.json"))
P={p["id"]:p for p in d["prompts"]}
out={}; tot=miss_all=sug_all=0
for pid,guesses in (TESTS2 if TIER=="2" else TESTS).items():
    ans=P[pid]["answers"]; ex={}; comp=[]
    for a in ans:
        labs=[a["n"],*(a.get("a") or [])]
        for l in labs:
            for f in forms(l): ex.setdefault(f,a)
        comp.append((a,[(stem(l) or norm(l)).replace(" ","") for l in labs]))
    rows=[]
    for g in guesses:
        hit=next((ex[f] for f in [norm(g),key(g),stem(g),key(g).replace(" ",""),stem(g).replace(" ","")] if f in ex),None)
        if hit: rows.append((g,"OK",hit["n"],hit["rarity"])); continue
        gg=stem(g).replace(" ",""); best=None
        if len(gg)>=4:
            for a,cs in comp:
                for c in cs:
                    b=budget(min(len(c),len(gg)))
                    if b and (dd:=lev(gg,c,b))<=b and (not best or dd<best[1]): best=(a,dd)
        rows.append((g,"SUGERE" if best else "FALTA", best[0]["n"] if best else "",None))
    m=sum(r[1]=="FALTA" for r in rows); s=sum(r[1]=="SUGERE" for r in rows)
    tot+=len(rows); miss_all+=m; sug_all+=s
    print(f"\n## {pid} ({P[pid]['text']}) pool={len(ans)} falta={m}/{len(rows)} sugere={s}")
    for r in rows: print("  ",r[1].ljust(6),r[0],"->",r[2], "" if r[3] is None else f"rar={r[3]:.2f}")
    out[pid]=rows
print(f"\nTOTAL falta {miss_all}/{tot} = {miss_all/tot:.0%}; só sugestão {sug_all}")
json.dump(out,open(ROOT/f"tools/research/miss_rate_t{TIER}.json","w"),ensure_ascii=False,indent=1)
