#include <Python.h>
//#include "_swizzle.h"
#include <patchlevel.h>

#if PY_MAJOR_VERSION < 3
#error "Module implemented for python 3 and up only."
#else
#define PY3 //to allow for compensating for non-backwards compatible python updates.
#endif

#define DIV_ROUND_UP(a, b) (((a) + (b) - 1) / (b))
#define round_up(a, b) ((((a) - 1) | ((b) - 1)) + 1)
#define assert(cond, msg, final) if (!(cond)) { \
{ final }; \
die(__FILE__ ":" __LINE__ ": " (msg)); \
}
#define assert(cond, msg) assert(cond, msg,)
#define assert(cond) assert(cond, "Assertation Failed!",)
#define try(cond) if (!(cond)) {\
return NULL;\
}

inline uint32_t getAddrBlockLinear(uint32_t x, uint32_t y, uint32_t image_width_in_gobs, uint8_t bytes_per_pixel, uint32_t base_address, uint32_t block_height):
    /*
    From the Tegra X1 TRM
    */

    uint32_t GOB_address = (base_address
                   + (y / (8 * block_height)) * 512 * block_height * image_width_in_gobs
                   + (x * bytes_per_pixel / 64) * 512 * block_height
                   + (y % (8 * block_height) / 8) * 512);

    x *= bytes_per_pixel;

    uint32_t Address = (GOB_address + ((x % 64) / 32) * 256 + ((y % 8) / 2) * 64
               + ((x % 32) / 16) * 32 + (y % 2) * 16 + (x % 16));

    return Address;
}
PyObject* _swizzle(uint32_t width, uint32_t height, uint32_t blkWidth, uint32_t blkHeight, uint8_t bpp, uint8_t tileMode, uint32_t alignment, uint8_t size_range, const Py_Buffer* buf, bool toSwizzle){
    uint32_t image_width_in_gobs = DIV_ROUND_UP(width * bpp, 64);
    assert(0 <= size_range <= 5);
    assert(buf->len >= width*height*bpp, "Not enough pixel data to unswizzle!");
    uint32_t block_height = 1 << size_range;
    const char* data = buf->buf;
    width = DIV_ROUND_UP(width, blkWidth);
    height = DIV_ROUND_UP(height, blkHeight);

    uint32_t pitch;
    uint32_t surfSize;

    if (tileMode == 0){
        pitch = round_up(width * bpp, 32);
        surfSize = round_up(pitch * height, alignment);
    } else {
        pitch = round_up(width * bpp, 64);
        surfSize = round_up(pitch * round_up(height, block_height * 8), alignment);
    }

    PyObject* callargs = Py_BuildValue("I", surfSize);
    PyObject* res = PyObject_CallObject(&PyBytearray_Type, callargs);
    Py_DECREF(callargs);
    assert(PuBuffer_CheckBuffer(res), "Allocation failure!");
    Py_buffer* buf = PyMem_Malloc(sizeof(*buf));
    int error = PyObject_GetBuffer(res, buf, PyBUF_SIMPLE);
    assert(error);
    assert(buf->len >= surfSize, "New Buffer not as big as requested?");
    assert(!buf->readonly, "New Buffer is not mutable?");
    char* result = buf->buf;
    
    for (int y = 0; y < height; y++){
        for (int x = 0; x < width; x++){
            if (tileMode == 0) {
                pos = y * pitch + x * bpp;
            } else {
                pos = getAddrBlockLinear(x, y, image_width_in_gobs, bpp, 0, block_height);
            }
            pos_ = (y * width + x) * bpp;

            if (pos + bpp <= surfSize) {
                if (toSwizzle) {
                    memcpy(result + pos, data + _pos, bpp);
                } else {
                    memcpy(result + _pos, data + pos, bpp);
                }
            }
        }
    }
    PyBuffer_Release(buf);
    PyMem_Free(buf); //we allocated it; so we can free it.
    return res;

PyObject* Py_Swizzle(PyObject* args){
    const Py_Buffer* src;
    size_t src_len;
    uint32_t width, height, blkwidth, blkheight, alignment;
    uint8_t bpp, tilemode, size_range;
    PyObject* toSwizzle;
    bool swizmode;
    try(PyArg_ParseTuple(args, "IIIIBBIIy*O", &width, &height, &blkwidth, &blkheight, &bpp, &tilemode, &alignment, &size_range, &src, &toSwizzle));
    assert(PyBool_Check(toSwizzle), "Not a Boolean", PyBuffer_Release(src));
    swizmode = Py_True == toSwizzle;
    PyObject* res = _swizzle(width, height, blkwidth, blkheight, bpp, tileMode, alignment, size_range, src, toSwizzle);
    PyBuffer_Release(src);
    return res;
}

static PyMethodDef functions[] = {
    {"swizzle_impl", (PyCFunction)Py_Swizzle, 1},
    {NULL, NULL}
};

PyMODINIT_FUNC
PyInit__swizzle(void){ 
    PyObject* m;
    static PyModuleDef module_def = {
        PyModuleDef_HEAD_INIT,
        "_swizzle",
        NULL,
        -1,
        functions,
    };
    m = PyModule_Create(&module_def)
    return m;

