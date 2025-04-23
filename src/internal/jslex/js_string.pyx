import cython

from cpython.list cimport PyList_New, PyList_SET_ITEM
from cpython.ref cimport PyObject
from cpython.unicode cimport PyUnicode_FromString
from libc.stdlib cimport free, malloc


cdef extern from "Python.h":
    object PyUnicode_FromStringAndSize(const char* u, Py_ssize_t size)

@cython.cdivision(True)
@cython.boundscheck(False)
@cython.wraparound(False)
def js_lexer_string(str js):
    """
    Find all JavaScript double-quoted strings in the input text.
    
    This is a Cython implementation of the regex pattern:
    r'"[^"\\]*(?:\\.[^"\\]*)*"'
    
    Args:
        js: The JavaScript source code to parse
        
    Returns:
        List of all double-quoted strings found
    """
    if not js:
        return []
    
    cdef:
        list results = []
        int start_pos = -1
        int i = 0
        int length = len(js)
        bint in_string = False
        bint escaped = False
        str current_str
    
    while i < length:
        if not in_string:
            # Looking for opening quote
            if js[i] == '"':
                start_pos = i
                in_string = True
                escaped = False
        else:
            # Already inside a string, looking for closing quote or handling escape
            if escaped:
                # Previous character was an escape, so current character is escaped
                escaped = False
            elif js[i] == '\\':
                # Found an escape character
                escaped = True
            elif js[i] == '"':
                # Found closing quote - capture the string
                current_str = js[start_pos:i+1]
                results.append(current_str)
                in_string = False
        
        i += 1
    
    return results
