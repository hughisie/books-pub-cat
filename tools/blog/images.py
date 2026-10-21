"""One-off image prep for the blog: resizes the public-domain / CC BY pictures into web sizes
and makes the 1200x630 social-share (Open Graph) cards. Run: python3 tools/blog/images.py <books-root>"""
import sys
from PIL import Image, ImageOps
root=sys.argv[1]
OUT='assets/img/blog/'
L=root+'/titles/loudun-nun-1644/images/'
C='/Users/m4owen/repos/pubcat-books/titles/chiromancy-1658/images/'
def web(src,name,w):
    im=Image.open(src).convert('RGB'); im.thumbnail((w,w*3)); im.save(OUT+name+'.webp','WEBP',quality=80); print(name,im.size)
def og(src,name,focus=(0.5,0.4)):
    im=Image.open(src).convert('RGB'); im=ImageOps.fit(im,(1200,630),method=Image.LANCZOS,centering=focus); im.save(OUT+name+'.jpg','JPEG',quality=84)
web(L+'02-grandier-burned-luyken-1701.jpg','possessed-grandier-burned-1701',1600)
web(L+'04-surin-isacaaron-poirson-1886.jpg','possessed-surin-isacaaron-1886',1000)
web(L+'13-lecon-clinique-salpetriere-brouillet-1887.jpg','possessed-clinical-lesson-1887',1600)
web(L+'20-facsimile-asmodeus-letter-in-her-hand.jpg','possessed-asmodeus-letter',1000)
web(C+'hand-1648-planets.jpg','chiromancy-hand-1648-planets',1000)
web(C+'hand-1501-hundt.jpg','chiromancy-hand-1501-hundt',1000)
web(C+'hands-1648-lines.jpg','chiromancy-hands-1648-lines',1000)
og(L+'02-grandier-burned-luyken-1701.jpg','og-possessed-blog',(0.5,0.45))
og(C+'hand-1648-planets.jpg','og-chiromancy-blog',(0.5,0.35))
