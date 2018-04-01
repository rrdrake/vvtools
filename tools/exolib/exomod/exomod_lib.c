#if 0
Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
(NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
Government retains certain rights in this software.
#endif

#include "Python.h"
#include <string.h>

const char * exm_create ( const char * filename, int mode, int convert_word_size, int file_word_size, int * exoid );
const char * exm_open ( const char * filename, int mode, int convert_word_size, int * file_word_size, float * version, int * exoid );
const char * exm_close ( int exoid );
const char * exm_get_init ( int exoid, char * title, int * counts );
const char * exm_inquire_counts ( int exoid, int * counts );
const char * exm_get_info ( int exoid, int num_info, char * info );
const char * exm_get_ids ( int exoid, int idtype, int * ids );
const char * exm_get_block ( int exoid, int btype, int bid, char * tname, int * counts );
const char * exm_get_set_param ( int exoid, int stype, int sid, int * nume, int * numdf );
const char * exm_get_qa ( int exoid, int num_qa, char * qabuf );
const char * exm_get_all_times ( int exoid, void * times );
const char * exm_get_var_params ( int exoid, int * counts );
const char * exm_get_all_var_names ( int exoid, char * global, char * node, char * edge, char * face, char * element, char * nodeset, char * edgeset, char * faceset, char * elemset, char * sideset );
const char * exm_get_truth_table ( int exoid, int var_type, int nblocks, int nvars, int * table );
const char * exm_get_coord_names ( int exoid, int ndim, char * names );
const char * exm_get_coord ( int exoid, void * xbuf, void * ybuf, void * zbuf );
const char * exm_get_conn ( int exoid, int block_type, int block_id, int conn_type, int * conn );
const char * exm_get_set ( int exoid, int set_type, int set_id, int * set_values, int * auxiliary );
const char * exm_get_set_dist_fact ( int exoid, int set_type, int set_id, void * values );
const char * exm_get_map ( int exoid, int map_type, int map_id, int * map_values );
const char * exm_get_glob_vars ( int exoid, int time_step, int num_global_vars, void * values );
const char * exm_get_nodal_var ( int exoid, int time_step, int var_idx, int num_nodes, void * values );
const char * exm_get_var ( int exoid, int time_step, int var_type, int var_idx, int block_id, int num_objects, void * values );
const char * exm_get_block_var ( int exoid, int time_step, int var_type, int var_idx, int num_ids, const int * block_ids, const int * num_objects, const int * is_stored, char storage, void * values );
const char * exm_get_var_time ( int exoid, int var_type, int var_idx, int obj_index, int beg_time_step, int end_time_step, void * values );
const char * exm_put_init ( int exoid, const char * title, const int * counts );
const char * exm_put_qa ( int exoid, int num_qa, char * qabuf );
const char * exm_put_info ( int exoid, int num_info, char * info );
const char * exm_put_coord_names ( int exoid, int ndim, const char * xname, const char * yname, const char * zname );
const char * exm_put_coord ( int exoid, const void * xbuf, const void * ybuf, const void * zbuf );
const char * exm_put_block ( int exoid, int block_type, int block_id, const char * block_type_name, int num_objects, int num_nodes_per_object, int num_edges_per_object, int num_faces_per_object, int num_attrs_per_object );
const char * exm_put_conn ( int exoid, int block_type, int block_id, int nodes_per_obj, int edges_per_obj, int faces_per_obj, const int * node_conn, const int * edge_conn, const int * face_conn );
const char * exm_put_set_param ( int exoid, int stype, int sid, int numobjs, int numdf );
const char * exm_put_set ( int exoid, int set_type, int set_id, const int * set_values, const int * auxiliary );
const char * exm_put_set_dist_fact ( int exoid, int set_type, int set_id, const void * values );
const char * exm_put_map ( int exoid, int map_type, int map_id, const int * map_values );
const char * exm_put_vars ( int exoid, int var_type, int num_vars, char * namebuf );
const char * exm_put_truth_table ( int exoid, int var_type, int nblocks, int nvars, const int * table );
const char * exm_put_time ( int exoid, int time_step, const void * time );
const char * exm_put_glob_vars ( int exoid, int time_step, int num_vars, const void * values );
const char * exm_put_nodal_var ( int exoid, int time_step, int var_idx, int num_nodes, const void * values );
const char * exm_put_var ( int exoid, int time_step, int var_type, int var_idx, int block_id, int num_objects, const void * values );

static char exm_create_lib_doc[] =
"  exm_create(string filename, int create_mode,\n"
"             int convert_word_size, int file_word_size, int* exoid )\n"
"    \n"
"    filename: the string file name to create\n"
"    create_mode: bit packed from EX_NOCLOBBER=0, EX_CLOBBER=1,\n"
"                 EX_NORMAL_MODEL=2, EX_LARGE_MODEL=4, EX_NETCDF4=8,\n"
"                 EX_NOSHARE=16, EX_SHARE=32 \n"
"    convert_word_size: either 4 or 8; all floating point arrays passed\n"
"                       through this interface are expected to have this\n"
"                       storage size; so if the 'file_word_size' value is \n"
"                       different, then the data will be converted\n"
"    file_word_size: size of floating point data stored in the file (4 or 8)\n"
"    exoid (OUT): the integer file descriptor of the new file";

static PyObject *
exm_create_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  const char * arg0;
  int arg1;
  int arg2;
  int arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "siiiw", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_create( arg0, arg1, arg2, arg3, (int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_open_lib_doc[] =
"  exm_open(string filename, int open_mode, int convert_word_size,\n"
"           int* file_word_size, float* version, int* exoid)\n"
"     \n"
"     filename: the string file name of an existing exodus file\n"
"     open_mode: either EX_READ=0 or EX_WRITE=1\n"
"     convert_word_size: if non-zero, then all floating point arrays passed\n"
"                        through this interface are expected to have this\n"
"                        storage size (either 4 or 8 bytes);  so if the file\n"
"                        has a different size, then the data will be converted\n"
"     file_word_size (OUT): 4 if the file stores single precision, 8 if double\n"
"     version (OUT): the Exodus version (a float)\n"
"     exoid (OUT): the integer file descriptor of the opened file";

static PyObject *
exm_open_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  const char * arg0;
  int arg1;
  int arg2;
  char * arg3;
  char * arg4;
  char * arg5;
  
  if ( !PyArg_ParseTuple( args, "siiwww", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5 ) )
    return NULL;
  
  serr = exm_open( arg0, arg1, arg2, (int *)arg3, (float *)arg4, (int *)arg5 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_close_lib_doc[] =
"  exm_close(int exoid)\n"
"  \n"
"     exoid: an integer file descriptor of an open exodus file";

static PyObject *
exm_close_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  
  if ( !PyArg_ParseTuple( args, "i", &arg0 ) )
    return NULL;
  
  serr = exm_close( arg0 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_init_lib_doc[] =
"  exm_get_init(int exoid, char* title, int* counts)\n"
"  \n"
"     'exoid' is an integer file descriptor of an open exodus file\n"
"     'title' a char buffer of length MAX_LINE_LENGTH+1 to hold the title\n"
"     'counts' an integer buffer of length 17 to hold each count:\n"
"         [ 0] = num_dim\n"
"         [ 1] = num_nodes\n"
"         [ 2] = num_edges\n"
"         [ 3] = num_edge_blk\n"
"         [ 4] = num_faces\n"
"         [ 5] = num_face_blk\n"
"         [ 6] = num_elems\n"
"         [ 7] = num_elem_blk\n"
"         [ 8] = num_node_sets\n"
"         [ 9] = num_edge_sets\n"
"         [10] = num_face_sets\n"
"         [11] = num_side_sets\n"
"         [12] = num_elem_sets\n"
"         [13] = num_node_maps\n"
"         [14] = num_edge_maps\n"
"         [15] = num_face_maps\n"
"         [16] = num_elem_maps";

static PyObject *
exm_get_init_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iww", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_get_init( arg0, (char *)arg1, (int *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_inquire_counts_lib_doc[] =
"  exm_inquire_counts(int exoid, int* counts_array)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     counts_array: an integer buffer of length 41 filled with the following\n"
"       [ 0] = number of dimensions\n"
"       [ 1] = number of nodes\n"
"       [ 2] = number of elements\n"
"       [ 3] = number of element blocks\n"
"       [ 4] = number of node sets\n"
"       [ 5] = length of node set node list\n"
"       [ 6] = number of side sets\n"
"       [ 7] = length of side set node list\n"
"       [ 8] = length of side set element list\n"
"       [ 9] = number of QA records\n"
"       [10] = number of info records\n"
"       [11] = number of time steps in the database\n"
"       [12] = number of element block properties\n"
"       [13] = number of node set properties\n"
"       [14] = number of side set properties\n"
"       [15] = length of node set distribution factor list\n"
"       [16] = length of side set distribution factor list\n"
"       [17] = number of element map properties\n"
"       [18] = number of node map properties\n"
"       [19] = number of element maps\n"
"       [20] = number of node maps\n"
"       [21] = number of edges\n"
"       [22] = number of edge blocks\n"
"       [23] = number of edge sets\n"
"       [24] = length of concat edge set edge list\n"
"       [25] = length of concat edge set dist factor list\n"
"       [26] = number of properties stored per edge block\n"
"       [27] = number of properties stored per edge set\n"
"       [28] = number of faces\n"
"       [29] = number of face blocks\n"
"       [30] = number of face sets\n"
"       [31] = length of concat face set face list\n"
"       [32] = length of concat face set dist factor list\n"
"       [33] = number of properties stored per face block\n"
"       [34] = number of properties stored per face set\n"
"       [35] = number of element sets\n"
"       [36] = length of concat element set element list\n"
"       [37] = length of concat element set dist factor list\n"
"       [38] = number of properties stored per elem set\n"
"       [39] = number of edge maps\n"
"       [40] = number of face maps";

static PyObject *
exm_inquire_counts_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  
  if ( !PyArg_ParseTuple( args, "iw", &arg0, &arg1 ) )
    return NULL;
  
  serr = exm_inquire_counts( arg0, (int *)arg1 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_info_lib_doc[] =
"  exm_get_info(int exoid, int num_info, char* info)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     num_info: the number of info records in the file\n"
"     info: a char buffer of size num_info*(MAX_LINE_LENGTH+1) where each\n"
"           line is sequential and uses MAX_LINE_LENGTH+1 characters and\n"
"           is padded with null characters";

static PyObject *
exm_get_info_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_get_info( arg0, arg1, (char *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_ids_lib_doc[] =
"  exm_get_ids(int exoid, int idtype, int* ids)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     idtype: one of EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK, EX_NODE_SET\n"
"             EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET, EX_NODE_MAP\n"
"             EX_EDGE_MAP, EX_FACE_MAP, or EX_ELEM_MAP\n"
"     ids: an integer buffer with length large enough to store the ids";

static PyObject *
exm_get_ids_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_get_ids( arg0, arg1, (int *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_block_lib_doc[] =
"  exm_get_block(int exoid, int block_type, int block_id,\n"
"                char* type_name, int* counts)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     block_type: one of EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK\n"
"     block_id: integer block id\n"
"     type_name: a char buffer to store the type of objects in the block, such\n"
"                as 'HEX'; must have length MAX_STR_LENGTH+1\n"
"     counts: an integer buffer of length 5\n"
"               [0] = num objects in the block\n"
"               [1] = num nodes per object\n"
"               [2] = num edges per object\n"
"               [3] = num faces per object\n"
"               [4] = num attributes per object";

static PyObject *
exm_get_block_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiww", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_get_block( arg0, arg1, arg2, (char *)arg3, (int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_set_param_lib_doc[] =
"  exm_get_set_param(int exoid, int set_type, int set_id,\n"
"                    int* num_objs, int* num_dist_factors)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,\n"
"               EX_SIDE_SET\n"
"     set_id: integer set id\n"
"     num_objs (OUT): number of objects in the set\n"
"     num_dist_factors (OUT): number of distribution factors";

static PyObject *
exm_get_set_param_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiww", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_get_set_param( arg0, arg1, arg2, (int *)arg3, (int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_qa_lib_doc[] =
"  exm_get_qa(int exoid, int num_qa, char* qa_records)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     num_qa: the number of QA records stored in the file\n"
"     qa_records: a char buffer with length 4*num_qa*(MAX_STR_LENGTH+1);\n"
"                 so that each record has 4 sequential entries each of length\n"
"                 MAX_STR_LENGTH+1 and the records are stored sequentially";

static PyObject *
exm_get_qa_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_get_qa( arg0, arg1, (char *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_all_times_lib_doc[] =
"  exm_get_all_times(int exoid, REAL* times)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     times: a floating point buffer of length equal to the number of time\n"
"            values; if the file stores doubles, then the buffer must store\n"
"            doubles, otherwise floats";

static PyObject *
exm_get_all_times_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  
  if ( !PyArg_ParseTuple( args, "iw", &arg0, &arg1 ) )
    return NULL;
  
  serr = exm_get_all_times( arg0, (void *)arg1 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_var_params_lib_doc[] =
"  exm_get_var_params(int exoid, int* counts)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     counts: an integer buffer of length 10 to store the number of variables\n"
"             of each type:\n"
"               [0] = num global vars,\n"
"               [1] = num node vars,\n"
"               [2] = num edge vars,\n"
"               [3] = num face vars,\n"
"               [4] = num element vars,\n"
"               [5] = num nodeset vars,\n"
"               [6] = num edgeset vars,\n"
"               [7] = num faceset vars,\n"
"               [8] = num element set vars,\n"
"               [9] = num sideset vars";

static PyObject *
exm_get_var_params_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  
  if ( !PyArg_ParseTuple( args, "iw", &arg0, &arg1 ) )
    return NULL;
  
  serr = exm_get_var_params( arg0, (int *)arg1 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_all_var_names_lib_doc[] =
"  exm_get_all_var_names(int exoid,  char* global,  char* node, char* edge,\n"
"                        char* face, char* element, char* nodeset,\n"
"                        char* edgeset, char* faceset, char* elemset,\n"
"                        char* sideset )\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     the rest are char buffers to hold the variable names for each var type;\n"
"     each must have length MAX_STR_LENGTH+1 times the number of variables\n"
"     of that type; they get filled with the names and padded on the right\n"
"     with NUL chars";

static PyObject *
exm_get_all_var_names_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  char * arg2;
  char * arg3;
  char * arg4;
  char * arg5;
  char * arg6;
  char * arg7;
  char * arg8;
  char * arg9;
  char * arg10;
  
  if ( !PyArg_ParseTuple( args, "iwwwwwwwwww", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6, &arg7, &arg8, &arg9, &arg10 ) )
    return NULL;
  
  serr = exm_get_all_var_names( arg0, (char *)arg1, (char *)arg2, (char *)arg3, (char *)arg4, (char *)arg5, (char *)arg6, (char *)arg7, (char *)arg8, (char *)arg9, (char *)arg10 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_truth_table_lib_doc[] =
"  exm_get_truth_table(int exoid, int var_type, int num_blocks,\n"
"                      int num_vars, int* table )\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,\n"
"               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET\n"
"     num_blocks: the number of blocks or sets stored for the var_type\n"
"     num_vars: the number of variables stored for the var_type\n"
"     table: an integer buffer of length num_blocks*num_vars to recieve the\n"
"            truth table values";

static PyObject *
exm_get_truth_table_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiiw", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_get_truth_table( arg0, arg1, arg2, arg3, (int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_coord_names_lib_doc[] =
"  exm_get_coord_names(int exoid, int ndim, char* names)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     ndim: the spatial dimension stored in the file\n"
"     names: char buffer to store the coordinate names;  must have length\n"
"            ndim*(MAX_STR_LENGTH+1); the name for the X coordinate is stored\n"
"            in the first MAX_STR_LENGTH+1 characters, then Y then Z.\n"
"            If the names are not stored in the file, then the string\n"
"            \"_not_stored_\" will be placed in the names buffer";

static PyObject *
exm_get_coord_names_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_get_coord_names( arg0, arg1, (char *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_coord_lib_doc[] =
"  exm_get_coord(int exoid, REAL* xbuf, REAL* ybuf, REAL* zbuf)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     xbuf, ybuf, zbuf: buffers for the X-, Y-, and Z-coordinates; the ybuf is\n"
"                       only used if the spatial dimension is 2 or 3; zbuf only\n"
"                       if dim is 3; if the file stores doubles, then the\n"
"                       buffers must store doubles as well, otherwise floats";

static PyObject *
exm_get_coord_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  char * arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iwww", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_get_coord( arg0, (void *)arg1, (void *)arg2, (void *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_conn_lib_doc[] =
"  exm_get_conn(int exoid, int block_type, int block_id, int conn_type,\n"
"               int* conn)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     block_type: one of  EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK\n"
"     block_id: the target block id\n"
"     conn_type: type of connections (one of EX_NODE, EX_EDGE, EX_FACE)\n"
"     conn: an integer buffer to store the connectivity matrix; the length\n"
"           must be num_objects*num_connections_per_object (such as\n"
"           num_elements*num_nodes_per_element)";

static PyObject *
exm_get_conn_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiiw", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_get_conn( arg0, arg1, arg2, arg3, (int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_set_lib_doc[] =
"  exm_get_set(int exoid, int set_type, int set_id,\n"
"              int* set_values, int* auxiliary)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,\n"
"               EX_SIDE_SET, EX_ELEM_SET\n"
"     set_id: the target set id\n"
"     set_values: the set values; length is the number of objects in the set\n"
"     auxiliary: unused for EX_NODE_SET and EX_ELEM_SET; must have same length\n"
"                as 'set_values' otherwise; stores +/- orientations for\n"
"                EX_EDGE_SET and EX_FACE_SET, or local side numbers for\n"
"                EX_SIDE_SET";

static PyObject *
exm_get_set_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiww", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_get_set( arg0, arg1, arg2, (int *)arg3, (int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_set_dist_fact_lib_doc[] =
"  exm_get_set_dist_fact(int exoid, int set_type, int set_id, REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,\n"
"               EX_SIDE_SET, EX_ELEM_SET\n"
"     set_id: the target set id\n"
"     values: the distribution factors; length is the number of objects in the\n"
"             set; the type is float if the file stores float, otherwise double";

static PyObject *
exm_get_set_dist_fact_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_get_set_dist_fact( arg0, arg1, arg2, (void *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_map_lib_doc[] =
"  exm_get_map(int exoid, int map_type, int map_id, int* map_values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     map_type: one of EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP\n"
"     map_id: the target map id\n"
"     map_values: the map values; length is the number of objects in the map";

static PyObject *
exm_get_map_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_get_map( arg0, arg1, arg2, (int *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_glob_vars_lib_doc[] =
"  exm_get_glob_vars(int exoid, int time_step, int num_global_vars, REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     num_global_vars: the number of global variables in the file\n"
"     values: the variable values; length must be 'num_global_vars'; the type\n"
"             is float if the file stores float, otherwise double";

static PyObject *
exm_get_glob_vars_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_get_glob_vars( arg0, arg1, arg2, (void *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_nodal_var_lib_doc[] =
"  exm_get_nodal_var(int exoid, int time_step, int var_idx,\n"
"                    int num_nodes, REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     var_idx: the variable index\n"
"     num_nodes: the number of nodes in the file\n"
"     values: the variable values; length must be 'num_nodes'; the type is\n"
"             float if the file stores float, otherwise double";

static PyObject *
exm_get_nodal_var_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiiw", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_get_nodal_var( arg0, arg1, arg2, arg3, (void *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_var_lib_doc[] =
"  exm_get_var(int exoid, int time_step, int var_type, int var_idx,\n"
"              int block_id, int num_objects, REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,\n"
"               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET\n"
"     var_idx: the variable index\n"
"     block_id: the id of the block or set\n"
"     num_objects: the number of objects in the block or set\n"
"     values: the variable values; length must be 'num_objects'; the type is\n"
"             float if the file stores float, otherwise double";

static PyObject *
exm_get_var_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  int arg4;
  int arg5;
  char * arg6;
  
  if ( !PyArg_ParseTuple( args, "iiiiiiw", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6 ) )
    return NULL;
  
  serr = exm_get_var( arg0, arg1, arg2, arg3, arg4, arg5, (void *)arg6 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_block_var_lib_doc[] =
"  exm_get_block_var(int exoid, int time_step, int var_type,\n"
"                    int var_idx, int num_ids, const int* block_ids,\n"
"                    const int* num_objects, const int* is_stored,\n"
"                    char storage, REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,\n"
"               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET\n"
"     var_idx: the variable index\n"
"     num_ids: the number of block or set ids\n"
"     block_id: length 'num_ids'; the ids of each block or set\n"
"     num_objects: length 'num_ids'; the number of objects in each block or set\n"
"     is_stored: length 'num_ids'; the truth table (true if the variable is\n"
"                stored in a given block id, false otherwise)\n"
"     storage: 'f' if the file stores floats, otherwise 'd' for double\n"
"     values: the variable values; length must be the sum of the entries in\n"
"             the 'num_objects' array; the type is float if the file stores\n"
"             float, otherwise double";

static PyObject *
exm_get_block_var_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  int arg4;
  char * arg5;
  char * arg6;
  char * arg7;
  char arg8;
  char * arg9;
  
  if ( !PyArg_ParseTuple( args, "iiiiiwwwcw", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6, &arg7, &arg8, &arg9 ) )
    return NULL;
  
  serr = exm_get_block_var( arg0, arg1, arg2, arg3, arg4, (const int *)arg5, (const int *)arg6, (const int *)arg7, arg8, (void *)arg9 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_get_var_time_lib_doc[] =
"  exm_get_var_time(int exoid, int var_type, int var_idx, int obj_index,\n"
"                   int beg_time_step, int end_time_step, REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     var_type: one of EX_GLOBAL, EX_NODE, EX_ELEM_BLOCK, EX_EDGE_BLOCK,\n"
"               EX_FACE_BLOCK, EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,\n"
"               EX_ELEM_SET, EX_SIDE_SET\n"
"     var_idx: the variable index\n"
"     obj_index: the 0-offset index of the desired object (the internal index)\n"
"     beg_time_step: staring time step number (time steps start at 1)\n"
"     end_time_step: ending time step number\n"
"     values: the variable values; length must be end_time_step-beg_time_step+1;\n"
"             the type is float if the file stores float, otherwise double";

static PyObject *
exm_get_var_time_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  int arg4;
  int arg5;
  char * arg6;
  
  if ( !PyArg_ParseTuple( args, "iiiiiiw", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6 ) )
    return NULL;
  
  serr = exm_get_var_time( arg0, arg1, arg2, arg3, arg4, arg5, (void *)arg6 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_init_lib_doc[] =
"  exm_put_init(int exoid, string title, int* counts)\n"
"  \n"
"     'exoid' is an integer file descriptor of an open exodus file\n"
"     'title' is the title string (only MAX_LINE_LENGTH characters are written)\n"
"     'counts' an integer buffer of length 17 containing each count:\n"
"         [ 0] = num_dim\n"
"         [ 1] = num_nodes\n"
"         [ 2] = num_edges\n"
"         [ 3] = num_edge_blk\n"
"         [ 4] = num_faces\n"
"         [ 5] = num_face_blk\n"
"         [ 6] = num_elems\n"
"         [ 7] = num_elem_blk\n"
"         [ 8] = num_node_sets\n"
"         [ 9] = num_edge_sets\n"
"         [10] = num_face_sets\n"
"         [11] = num_side_sets\n"
"         [12] = num_elem_sets\n"
"         [13] = num_node_maps\n"
"         [14] = num_edge_maps\n"
"         [15] = num_face_maps\n"
"         [16] = num_elem_maps";

static PyObject *
exm_put_init_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  const char * arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "isw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_put_init( arg0, arg1, (const int *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_qa_lib_doc[] =
"  exm_put_qa(int exoid, int num_qa, char* qabuf)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     num_qa: the number of QA records to store\n"
"     qabuf: a char buffer containing the QA records;  there must be\n"
"            4*num_qa null terminated strings concatenated together";

static PyObject *
exm_put_qa_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_put_qa( arg0, arg1, (char *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_info_lib_doc[] =
"  exm_put_info(int exoid, int num_info, char* info)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     num_info: the number of info records in the file\n"
"     info: a char buffer containing the QA records;  there must be\n"
"            num_info null terminated strings concatenated together";

static PyObject *
exm_put_info_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_put_info( arg0, arg1, (char *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_coord_names_lib_doc[] =
"  exm_put_coord_names(int exoid, int ndim, const char* xname,\n"
"                      const char* yname, const char* zname)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     ndim: the spatial dimension stored in the file\n"
"     xname, yname, zname: char buffers containing the coordinate names;  only\n"
"                          xname used if dim is one, xname and yname if dim is\n"
"                          two, and all three if dim is three";

static PyObject *
exm_put_coord_names_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  const char * arg2;
  const char * arg3;
  const char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iisss", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_put_coord_names( arg0, arg1, arg2, arg3, arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_coord_lib_doc[] =
"  exm_put_coord(int exoid, REAL* xbuf, REAL* ybuf, REAL* zbuf)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     xbuf, ybuf, zbuf: buffers for the X-, Y-, and Z-coordinates; the ybuf is\n"
"                       only used if the spatial dimension is 2 or 3; zbuf only\n"
"                       if dim is 3; if the file stores doubles, then the\n"
"                       buffers must store doubles as well, otherwise floats";

static PyObject *
exm_put_coord_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  char * arg1;
  char * arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iwww", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_put_coord( arg0, (const void *)arg1, (const void *)arg2, (const void *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_block_lib_doc[] =
"  exm_put_block(int exoid, int block_type, int block_id,\n"
"                const char* block_type_name, int num_objects,\n"
"                int num_nodes_per_object, int num_edges_per_object,\n"
"                int num_faces_per_object, int num_attrs_per_object)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     block_type:  one of EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK\n"
"     block_id:  the integer block id\n"
"     block_type_name:  a string describing the object types (such as HEX8)\n"
"     num_objects:  number of objects/entries in this block\n"
"     num_nodes_per_object:  local number of nodes per object\n"
"     num_edges_per_object:  local number of edges per object\n"
"     num_faces_per_object:  local number of faces per object\n"
"     num_attrs_per_object:  number of attributes for each object";

static PyObject *
exm_put_block_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  const char * arg3;
  int arg4;
  int arg5;
  int arg6;
  int arg7;
  int arg8;
  
  if ( !PyArg_ParseTuple( args, "iiisiiiii", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6, &arg7, &arg8 ) )
    return NULL;
  
  serr = exm_put_block( arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_conn_lib_doc[] =
"  exm_put_conn(int exoid, int block_type, int block_id,\n"
"               int nodes_per_obj, int edges_per_obj, int faces_per_obj,\n"
"               const int* node_conn, const int* edge_conn,\n"
"               const int* face_conn)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     block_type: one of  EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK\n"
"     block_id: the target block id\n"
"     nodes_per_obj: number of local nodes per object\n"
"     edges_per_obj: number of local edges per object\n"
"     faces_per_obj: number of local faces per object\n"
"     node_conn: an integer buffer to store the node connectivity matrix;\n"
"                the length must be num_objects*nodes_per_object\n"
"                (such as num_elements*num_nodes_per_element)\n"
"     edge_conn: an integer buffer to store the edge connectivity matrix;\n"
"                the length must be num_objects*edges_per_object\n"
"     face_conn: an integer buffer to store the face connectivity matrix;\n"
"                the length must be num_objects*faces_per_object";

static PyObject *
exm_put_conn_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  int arg4;
  int arg5;
  char * arg6;
  char * arg7;
  char * arg8;
  
  if ( !PyArg_ParseTuple( args, "iiiiiiwww", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6, &arg7, &arg8 ) )
    return NULL;
  
  serr = exm_put_conn( arg0, arg1, arg2, arg3, arg4, arg5, (const int *)arg6, (const int *)arg7, (const int *)arg8 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_set_param_lib_doc[] =
"  exm_put_set_param(int exoid, int set_type, int set_id,\n"
"                    int num_objs, int num_dist_factors)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,\n"
"               EX_SIDE_SET\n"
"     set_id: integer set id\n"
"     num_objs: number of objects in the set\n"
"     num_dist_factors: number of distribution factors";

static PyObject *
exm_put_set_param_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  int arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiii", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_put_set_param( arg0, arg1, arg2, arg3, arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_set_lib_doc[] =
"  exm_put_set(int exoid, int set_type, int set_id,\n"
"              const int* set_values, const int* auxiliary)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,\n"
"               EX_SIDE_SET, EX_ELEM_SET\n"
"     set_id: the target set id\n"
"     set_values: the set values; length is the number of objects in the set\n"
"     auxiliary: unused for EX_NODE_SET and EX_ELEM_SET; must have same length\n"
"                as 'set_values' otherwise; stores +/- orientations for\n"
"                EX_EDGE_SET and EX_FACE_SET, or local side numbers for\n"
"                EX_SIDE_SET";

static PyObject *
exm_put_set_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiww", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_put_set( arg0, arg1, arg2, (const int *)arg3, (const int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_set_dist_fact_lib_doc[] =
"  exm_put_set_dist_fact(int exoid, int set_type, int set_id, const REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,\n"
"               EX_SIDE_SET, EX_ELEM_SET\n"
"     set_id: the target set id\n"
"     values: the distribution factors; length is the number of objects in the\n"
"             set; the type is float if the file stores float, otherwise double";

static PyObject *
exm_put_set_dist_fact_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_put_set_dist_fact( arg0, arg1, arg2, (const void *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_map_lib_doc[] =
"  exm_put_map(int exoid, int map_type, int map_id, const int* map_values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     map_type: one of EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP\n"
"     map_id: the target map id\n"
"     map_values: the map values; length is the number of objects in the map";

static PyObject *
exm_put_map_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_put_map( arg0, arg1, arg2, (const int *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_vars_lib_doc[] =
"  exm_put_vars(int exoid, int var_type, int num_vars, char* namebuf)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     var_type: one of EX_GLOBAL, EX_NODAL, EX_ELEM_BLOCK, EX_EDGE_BLOCK,\n"
"               EX_FACE_BLOCK, EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,\n"
"               EX_ELEM_SET, EX_SIDE_SET, where EX_NODAL == 15\n"
"     num_vars: number of variable names to be written\n"
"     namebuf: a char buffer containing the sequence of names, each string\n"
"              must be terminated with a NUL char; the number of names must\n"
"              match the 'num_vars' value; note that the char buffer may be\n"
"              modified to restrict the name lengths to a max of MAX_STR_LENGTH";

static PyObject *
exm_put_vars_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_put_vars( arg0, arg1, arg2, (char *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_truth_table_lib_doc[] =
"  exm_put_truth_table(int exoid, int var_type, int num_blocks,\n"
"                      int num_vars, const int* table )\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,\n"
"               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET\n"
"     num_blocks: the number of blocks or sets stored for the var_type\n"
"     num_vars: the number of variables stored for the var_type\n"
"     table: an integer buffer of length num_blocks*num_vars containing the\n"
"            truth table values; the variable index cycles faster than the\n"
"            block index";

static PyObject *
exm_put_truth_table_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiiw", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_put_truth_table( arg0, arg1, arg2, arg3, (const int *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_time_lib_doc[] =
"  exm_put_time(int exoid, int time_step, const REAL* time)\n"
"  \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time steps begin at one (1)\n"
"     time: a length one array storing the floating point time value;  if the\n"
"           file stores doubles, then it must store a double, otherwise a float";

static PyObject *
exm_put_time_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  char * arg2;
  
  if ( !PyArg_ParseTuple( args, "iiw", &arg0, &arg1, &arg2 ) )
    return NULL;
  
  serr = exm_put_time( arg0, arg1, (const void *)arg2 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_glob_vars_lib_doc[] =
"  exm_put_glob_vars(int exoid, int time_step, int num_vars, const REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     num_vars: the number of global variables in the file\n"
"     values: the variable values; length must be 'num_vars'; the type\n"
"             is float if the file stores float, otherwise double";

static PyObject *
exm_put_glob_vars_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  char * arg3;
  
  if ( !PyArg_ParseTuple( args, "iiiw", &arg0, &arg1, &arg2, &arg3 ) )
    return NULL;
  
  serr = exm_put_glob_vars( arg0, arg1, arg2, (const void *)arg3 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_nodal_var_lib_doc[] =
"  exm_put_nodal_var(int exoid, int time_step, int var_idx,\n"
"                    int num_nodes, const REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     var_idx: the variable index\n"
"     num_nodes: the number of nodes in the file\n"
"     values: the variable values; length must be 'num_nodes'; the type is\n"
"             float if the file stores float, otherwise double";

static PyObject *
exm_put_nodal_var_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  char * arg4;
  
  if ( !PyArg_ParseTuple( args, "iiiiw", &arg0, &arg1, &arg2, &arg3, &arg4 ) )
    return NULL;
  
  serr = exm_put_nodal_var( arg0, arg1, arg2, arg3, (const void *)arg4 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

static char exm_put_var_lib_doc[] =
"  exm_put_var(int exoid, int time_step, int var_type, int var_idx,\n"
"              int block_id, int num_objects, const REAL* values)\n"
"     \n"
"     exoid: an open exodus file descriptor\n"
"     time_step: time step number (they start at 1)\n"
"     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,\n"
"               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET\n"
"     var_idx: the variable index\n"
"     block_id: the id of the block or set\n"
"     num_objects: the number of objects in the block or set\n"
"     values: the variable values; length must be 'num_objects'; the type is\n"
"             float if the file stores float, otherwise double";

static PyObject *
exm_put_var_lib( PyObject* self, PyObject* args )
{
  const char * serr;
  int arg0;
  int arg1;
  int arg2;
  int arg3;
  int arg4;
  int arg5;
  char * arg6;
  
  if ( !PyArg_ParseTuple( args, "iiiiiiw", &arg0, &arg1, &arg2, &arg3, &arg4, &arg5, &arg6 ) )
    return NULL;
  
  serr = exm_put_var( arg0, arg1, arg2, arg3, arg4, arg5, (const void *)arg6 );
  if ( serr != NULL ) {
    PyErr_SetString(PyExc_Exception, serr);
    return NULL;
  }
  
  Py_INCREF( Py_None );
  return Py_None;
}

/*********************************************/

static PyMethodDef exomod_lib_methods[] = {
  { "exm_create", exm_create_lib, METH_VARARGS, exm_create_lib_doc },
  { "exm_open", exm_open_lib, METH_VARARGS, exm_open_lib_doc },
  { "exm_close", exm_close_lib, METH_VARARGS, exm_close_lib_doc },
  { "exm_get_init", exm_get_init_lib, METH_VARARGS, exm_get_init_lib_doc },
  { "exm_inquire_counts", exm_inquire_counts_lib, METH_VARARGS, exm_inquire_counts_lib_doc },
  { "exm_get_info", exm_get_info_lib, METH_VARARGS, exm_get_info_lib_doc },
  { "exm_get_ids", exm_get_ids_lib, METH_VARARGS, exm_get_ids_lib_doc },
  { "exm_get_block", exm_get_block_lib, METH_VARARGS, exm_get_block_lib_doc },
  { "exm_get_set_param", exm_get_set_param_lib, METH_VARARGS, exm_get_set_param_lib_doc },
  { "exm_get_qa", exm_get_qa_lib, METH_VARARGS, exm_get_qa_lib_doc },
  { "exm_get_all_times", exm_get_all_times_lib, METH_VARARGS, exm_get_all_times_lib_doc },
  { "exm_get_var_params", exm_get_var_params_lib, METH_VARARGS, exm_get_var_params_lib_doc },
  { "exm_get_all_var_names", exm_get_all_var_names_lib, METH_VARARGS, exm_get_all_var_names_lib_doc },
  { "exm_get_truth_table", exm_get_truth_table_lib, METH_VARARGS, exm_get_truth_table_lib_doc },
  { "exm_get_coord_names", exm_get_coord_names_lib, METH_VARARGS, exm_get_coord_names_lib_doc },
  { "exm_get_coord", exm_get_coord_lib, METH_VARARGS, exm_get_coord_lib_doc },
  { "exm_get_conn", exm_get_conn_lib, METH_VARARGS, exm_get_conn_lib_doc },
  { "exm_get_set", exm_get_set_lib, METH_VARARGS, exm_get_set_lib_doc },
  { "exm_get_set_dist_fact", exm_get_set_dist_fact_lib, METH_VARARGS, exm_get_set_dist_fact_lib_doc },
  { "exm_get_map", exm_get_map_lib, METH_VARARGS, exm_get_map_lib_doc },
  { "exm_get_glob_vars", exm_get_glob_vars_lib, METH_VARARGS, exm_get_glob_vars_lib_doc },
  { "exm_get_nodal_var", exm_get_nodal_var_lib, METH_VARARGS, exm_get_nodal_var_lib_doc },
  { "exm_get_var", exm_get_var_lib, METH_VARARGS, exm_get_var_lib_doc },
  { "exm_get_block_var", exm_get_block_var_lib, METH_VARARGS, exm_get_block_var_lib_doc },
  { "exm_get_var_time", exm_get_var_time_lib, METH_VARARGS, exm_get_var_time_lib_doc },
  { "exm_put_init", exm_put_init_lib, METH_VARARGS, exm_put_init_lib_doc },
  { "exm_put_qa", exm_put_qa_lib, METH_VARARGS, exm_put_qa_lib_doc },
  { "exm_put_info", exm_put_info_lib, METH_VARARGS, exm_put_info_lib_doc },
  { "exm_put_coord_names", exm_put_coord_names_lib, METH_VARARGS, exm_put_coord_names_lib_doc },
  { "exm_put_coord", exm_put_coord_lib, METH_VARARGS, exm_put_coord_lib_doc },
  { "exm_put_block", exm_put_block_lib, METH_VARARGS, exm_put_block_lib_doc },
  { "exm_put_conn", exm_put_conn_lib, METH_VARARGS, exm_put_conn_lib_doc },
  { "exm_put_set_param", exm_put_set_param_lib, METH_VARARGS, exm_put_set_param_lib_doc },
  { "exm_put_set", exm_put_set_lib, METH_VARARGS, exm_put_set_lib_doc },
  { "exm_put_set_dist_fact", exm_put_set_dist_fact_lib, METH_VARARGS, exm_put_set_dist_fact_lib_doc },
  { "exm_put_map", exm_put_map_lib, METH_VARARGS, exm_put_map_lib_doc },
  { "exm_put_vars", exm_put_vars_lib, METH_VARARGS, exm_put_vars_lib_doc },
  { "exm_put_truth_table", exm_put_truth_table_lib, METH_VARARGS, exm_put_truth_table_lib_doc },
  { "exm_put_time", exm_put_time_lib, METH_VARARGS, exm_put_time_lib_doc },
  { "exm_put_glob_vars", exm_put_glob_vars_lib, METH_VARARGS, exm_put_glob_vars_lib_doc },
  { "exm_put_nodal_var", exm_put_nodal_var_lib, METH_VARARGS, exm_put_nodal_var_lib_doc },
  { "exm_put_var", exm_put_var_lib, METH_VARARGS, exm_put_var_lib_doc },
  { NULL, NULL, 0, NULL } /* Sentinel */
};

DL_EXPORT(void) initexomod_lib(void) {
  (void) Py_InitModule( "exomod_lib", exomod_lib_methods );
}
