try:
  #the latter of these is for the pixel format PyDecoder...
  from PIL import ImageFile, Image, _imaging as PyImaging
  pil = True
except ImportError: #note that *one* of these must be present...
  #this is a GIMP plugin
  from gimpfu import *
  import io
  pil = False
import struct
from .bntx_extract import BNTXHeader, NXHeader, BRTIInfo #import the types...
from . import bntx_extract #and then import the namespace itself.
from . import swizzle #this handles C acceleration itself.
try:
  import astc_codec #this registers with PIL, so we don't need to do anything else
  astc = True
except ImportError:
  astc = False

DEBUG = False


#we effectively *become* the BCn decoder for swizzled textures
#since we can call the superclass.
class BntxSwizzler(ImageFile.PyDecoder if pil else object):
  if not pil:
    def __init__(self, buf, args = None):
      self.fd = io.BytesIO(buf)
  def init(self, args):
    self.mode = "RGBA"
    self.start = True
    self.args = args
    self._pulls_fd = True #*way* easier...
    if not pil: #FIXME: don't rely on this for gimp.
      raise NotImplementedError("Standalone BCN decoder not implemented!")

  def decode(self, buffer):
    global DEBUG
    tex = self.args[0] #it's not a "real" TexInfo, but the fields are the named the same, so duck typing saves the day!
    assert self.fd, "Something in PIL broke '_pulls_fd'! contact maintainer."
    buf = self.fd.read()
    bpp = bntx_extract.bpps[tex.format_ >> 8]
    if (tex.format_ >>8) in bntx_extract.blk_dims:
      blkWidth, blkHeight = bntx_extract.blk_dims[tex.format_ >>8]
    else:
      blkWidth, blkHeight = (1, 1)
    assert self.im is not None, "don't have an image before decode was called?"
    width, height = self.im.size
    size = swizzle.DIV_ROUND_UP(tex.width, blkWidth) * swizzle.DIV_ROUND_UP(tex.height, blkHeight) * bpp
    buf = swizzle.deswizzle(width, height, blkWidth, blkHeight, bpp, tex.tileMode, tex.alignment, tex.sizeRange, buf)
    buf = bytes(buf[:size])
    if DEBUG:
      print("Swizzle size:",size)
      print("Output buffer size:",len(buf))
    if pil:
      if (tex.format_ >>8) > 0x19 and (tex.format_ >>8) < 0x21:
        bcmode = (tex.format_ >> 8)- 0x19 #yes, this actually works; 0x1a is BC1, 1b is BC2, etc.
        if DEBUG:
          print("BC[N] n-value:", bcmode)
      elif tex.format_ >> 8 in bntx_extract.BCn_formats:
        raise NotImplementedError("Unknown BlockCompression format. contact maintainer with sample.")
      if (tex.format_ >> 8) in bntx_extract.ASTC_formats:
        if astc: #do we have the optional codec?
          self.superdec = Image._getdecoder(self.mode, 'astc', (blkWidth, blkHeight))
        else:
          raise KeyError("This is an ASTC image, but the codec is not installed. please install 'astc_codec' with pip.")
      else:
        self.superdec = Image._getdecoder(self.mode, 'bcn', (bcmode,))
      self.superdec.setimage(self.im, self.state.extents())
      s = self.superdec.decode(buf)
      if s[0] >= 0:
        raise ValueError("not enough image data")
      if s[1] != 0:
        raise ValueError("cannot decode image data")
      return s
    else:
      raise NotImplementedError("FIXME: non-PIL decoding of BC[n] pixelformats")
    

#support for multi-image is a bit iffy. (and undocumented)
#make the class standalone if PIL isn't available
class BntxImageFile(ImageFile.ImageFile if pil else object): 
  format = "BNTX"
  format_description = "Nintendo BNTX Multi-Texture"
  #this isn't working for some reason?
  _close_exclusive_fp_after_loading = False #this isn't documented for some reason?

  if not pil:
    def __init__(self, fd): #shim constructor if we're not using PIL
      global DEBUG
      if DEBUG:
        print("BNTX: Standalone BntxImageFile created.")
      self.fp = fd
      self._open()
  def _open(self):
    global pil
    global DEBUG
    fd = self.fp
    self.fd = fd
    dat = fd.read(32) #size of BNTX struct
    if dat[0xc:0xe] == b'\xFF\xFE':
        if DEBUG:
          print("BNTX: Little Endian")
        bom = '<'

    elif dat[0xc:0xe] == b'\xFE\xFF':
        if DEBUG:
          print("BNTX: Big Endian")
        bom = '>'

    else:
        raise SyntaxError("Invalid BOM!")
    self.bom = bom
    head = BNTXHeader(bom)
    head.data(dat, 0)
    assert head.magic[0:4] == b'BNTX', "Invalid BNTX Magic, is " + str(head.magic)
    nx = NXHeader(bom)
    nx.data(fd.read(36), 0)
    self._n_frames = nx.count
    self.num_frames = nx.count
    width, height = (0,0)
    if DEBUG:
      print("BNTX: Frame count:",nx.count)
    frames = []
    for i in range(nx.count):
      frame = BRTIInfo(bom)
      pos = nx.infoPtrAddr + i*8
      fd.seek(pos)
      pos = struct.unpack(bom + 'q', fd.read(8))[0]
      fd.seek(pos)
      frame.data(fd.read(frame.size), 0)
      frames.append(frame)
    for frame in frames: #get the largest dimensions of all textures.
      if frame.width > width:
        width = frame.width
      if frame.height > height:
        height = frame.height
    #self._size = int(width), int(height)
    self._frames = frames
    self.tile = None
    if DEBUG:
      print("BNTX: PIL state:",pil)
    if pil: #only use PIL's multi-frame architecture if we *need* to. gimp can load it all at once.
      if DEBUG:
        print("BNTX: First call to seek as part of initial open.")
      self.seek(0) #and load the first frame tile

  def load_end(self):
    if self.__frame == 0 and self._n_frames == 1:
      self._close_exclusive_fp_after_loader = True #again, undocumented.

  #this does weird things; turn it off for now...
  #def load(self):
  #  if self.tile is None:
  #    raise IOError("Cannot load image")
  #  if not len(self.tile) == 1:
  #    raise IOError("More than one tile somehow? " + str(len(self.tile)))
  #  return super(BntxImageFile, self).load()

  @property
  def n_frames(self):
    return self._n_frames
    
  def seek(self, frame):
    global DEBUG
    if not frame < self._n_frames:
      raise EOFError("Invalid BNTX Frame")
    self.__frame = frame
    if DEBUG:
      print("BNTX: Seeking to frame",frame)
    self._setup()

  def tell(self):
    return self.__frame

  #_setup and seek don't get used under gimp.
  def _setup(self): #read the current texture and setup the tile info accordingly
    global DEBUG
    fd = self.fd
    self.fp = fd #why the hell does this get reset?
    bom = self.bom
    f = self._frames[self.__frame]
    info = f
    fd.seek(info.ptrsAddr)
    mips = {0: 0} #mipmap data. TODO: what to do with this?
    offset = struct.unpack(bom + 'q', fd.read(8))[0]
    if DEBUG:
      print("Number of mipmaps in this texture:",info.numMips)
    for i in range(1, info.numMips):
      moffset = struct.unpack(bom+'q', fd.read(8))[0]
      mips[i] = moffset - offset
    self.mode = "RGBA" #yes, this is constant. for DXT images at least.
    self._size = (f.width,f.height) #abuse the mutability of python to alter the image dimensions on the fly
    
    self.tile = [("bntx",(0,0) + (f.width, f.height),offset,(f,(1,)))] #this takes both swizzle and unswizzle
    if DEBUG:
      print(self.tile)
    
if pil: #we're a PIL plugin; register with PIL.
  if DEBUG:
    print("Registering PIL handles...")
  Image.register_decoder("bntx", BntxSwizzler)
  Image.register_open("BNTX", BntxImageFile)
  Image.register_extension("BNTX", ".bntx")

else: #we're a gimp plugin; define the required bits and register with gimp.
  if DEBUG:
    print("!FIXME! !NotImplemented! Registering with GIMP/Glimpse...")
  def load_bntx(filename, raw_filename):
    with open(filename, 'rb') as fd:
      width, height = (0, 0)
      bntx = BntxImageFile(fd)
      for frame in bntx.frames: #get the largest dimensions for the canvas
        if frame.width > width:
          width = frame.width
        if frame.height > height:
          height = frame.height
      img = gimp.Image(width, height, RGB) #it will always be RGB by the time gimp gets it.
      img.filename = filename
      for frame in bntx.frames:
        pixbyte = 3 #FIXME: determine at runtime
        fd.seek(frame.nameAddr) #get subtexture name for layer name
        name = fd.read(struct.unpack(bntx.bom + 'H', fd.read(2))).decode('utf-8').rstrip('\x00')
        layer = gimp.Layer(img, name, frame.width, frame.height, RGB_IMAGE, 100)
        layer.set_offsets(0,0)
        #TODO: should we load mipmaps?
        
      
        assert layer.bpp == 8
        pr = layer.get_pixel_rgn(0,0,frame.width,frame.height)
        pr[:,:] = framebuf
        img.add_layer(layer)


if __name__ == "__main__": #standalone test mode; we use PIL for this.
  import sys
  img = Image.open(open(sys.argv[1],'rb')) #make it a non-exclusive fd so things actually *keep it open*.
  for i in range(img.num_frames):
    img.seek(i)
    img.show()

