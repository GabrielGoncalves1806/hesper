from PIL import Image
import sys
P="reports/design/v07_lore/pendentes/"
ids="table chair crate sign chair_fallen lab_bench microscope sample_shelf bunk locker console sample_tank rubble ice_stain dead_plant barrel".split()
k=4
im=Image.new("RGBA",(8*(32*k+8)+8,2*(40*k+16*k+24)+8),(120,100,90,255))
for n,i in enumerate(ids):
    x=8+(n%8)*(32*k+8); y=8+(n//8)*(40*k+16*k+24)
    s=Image.open(P+f"prop_{i}.png"); im.alpha_composite(s.resize((s.width*k,s.height*k),Image.NEAREST),(x,y))
    s=Image.open(P+f"icon_prop_{i}.png"); im.alpha_composite(s.resize((s.width*k,s.height*k),Image.NEAREST),(x,y+40*k+4))
im.save(sys.argv[1])
