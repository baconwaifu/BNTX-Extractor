#!/usr/bin/env python3
from PIL import Image #this needs to come before BNTX, so this instance is what gets mutated.
from . import bntx_pil as bntx
import sys
import io

#*technically* this works for any format PIL supports...
def bntx_view(fd, args):
  img = Image.open(fd)
  for i in range(img.num_frames):
    img.seek(i)
    img.show()

def bntx_convert(fd, args):
  if len(args) > 1:
    outname = args[1]
  else:
    outname = args[0].split('.')[:-1] + ".png"
  img = Image.open(fd)
  img.save(outname, "PNG")

def bntx_info(fd, args):
  img = Image.open(fd)
  print(isinstance(img,bntx.BntxImageFile))
  raise NotImplementedError("TODO: figure out a way to get the structs out of Image.open()")

#only thumnails the first frame
def bntx_thumbnail(fd, args):
  assert len(args) == 3
  size = int(args[2])
  size = (size,size)
  outfile = args[1]
  img = Image.open(fd)
  img.thumbnail(size, Image.ANTIALIAS)
  img.save(outfile,"PNG")

if __name__ == "__main__":
  ops = {
    "view": bntx_view,
    "png": bntx_convert,
    "2png": bntx_convert,
    "convert": bntx_convert,
    "info": bntx_info,
    "thumbnail": bntx_thumbnail
  }
  if len(sys.argv) < 3:
    print("Usage: bntx <op> <file> [args]")
    sys.exit(1)
  if sys.argv[1] in ops: #this first in case someone forgets to say `extract`...
    fd = open(sys.argv[2], 'rb')
    ops[sys.argv[1]](fd,sys.argv[2:]) #args[0] is the filename. useful for some functions guessing suitable output names
  else: #cleanly catch invalid operations
    print ("Invalid operation",sys.argv[1],"\nValid operations are:")
    for key, func in ops.items():
      print(key)
    sys.exit(2)
