import re
def frame_chk(hexstr):
    b=bytes.fromhex(hexstr)
    print('len',len(b),'head',b[:4].hex(),'tail',b[-3:].hex())
    for name,val in [
        ('sum(all-but-tail2)&0xff', sum(b[:-2])&0xff),
        ('sum(head+ascii)&0xff', sum(b[:-2])&0xff),
        ('sum(ascii)&0xff', sum(b[3:-2])&0xff),
        ('sum(all)&0xff', sum(b)&0xff),
        ('xor(ascii)', __import__('functools').reduce(lambda a,c:a^c, b[3:-2],0)),
        ('xor(all-but-tail2)', __import__('functools').reduce(lambda a,c:a^c, b[:-2],0)),
    ]:
        print(' ',name,hex(val),val)
# conn frame
conn='5A0038504F535420636F6E6E20310D0A5365714E756D6265723D333739320D0A446174653D313739333037373339353234340D0A0D0A055A'
frame_chk(conn)
# ack frame (AckNumber=3794)
ack='5A004131203230300D0A41636B4E756D6265723D333739340D0A436F6E74656E744C656E6774683D300D0A436F6E74656E74547970653D6A736F6E0D0A0D0A415A'
frame_chk(ack)
