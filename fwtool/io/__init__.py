import os

class FilePart:
 """A view of a part of a file. Can be used like a regular file"""
 def __init__(self, file, offset=0, size=-1):
  if size < 0:
   file.seek(0, os.SEEK_END)
   size = file.tell() - offset
  self.file = file
  self.offset = offset
  self.size = size
  self.pos = 0

 def seek(self, pos, ref=os.SEEK_SET):
  if ref == os.SEEK_SET:
   self.pos = pos
  elif ref == os.SEEK_CUR:
   self.pos += pos
  elif ref == os.SEEK_END:
   self.pos = self.size + pos
  pos = min(max(pos, 0), self.size)

 def tell(self):
  return self.pos

 def read(self, size=-1):
  if size < 0:
   size = self.size
  self.file.seek(self.offset + self.pos)
  data = self.file.read(min(size, self.size - self.pos))
  self.pos += len(data)
  return data
