
#if 0
Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
(NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
Government retains certain rights in this software.
#endif

#include "exodusII.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static char* exm_errstr = 0;
static int   exm_errstr_len = 0;
static const char* exm_get_error_string(void)
{
  const char* msg;
  const char* func;
  int errcode;
  
  ex_get_err( &msg, &func, &errcode );
  
  if ( strlen(msg) + strlen(func) + 3 + 46 + 1 > exm_errstr_len )
  {
    exm_errstr_len = strlen(msg) + strlen(func) + 3 + 33 + 1;
    
    if ( exm_errstr != NULL )
      free( exm_errstr );
    
    exm_errstr = (char*) malloc( exm_errstr_len );
    
    if ( exm_errstr == NULL )
      return msg;
  }
  
  sprintf( exm_errstr, "[%s, err=%d] %s", func, errcode, msg );
  
  return exm_errstr;
}

/*
GENMOD: DOC:
  exm_create(string filename, int create_mode,
             int convert_word_size, int file_word_size, int* exoid )
    
    filename: the string file name to create
    create_mode: bit packed from EX_NOCLOBBER=0, EX_CLOBBER=1,
                 EX_NORMAL_MODEL=2, EX_LARGE_MODEL=4, EX_NETCDF4=8,
                 EX_NOSHARE=16, EX_SHARE=32 
    convert_word_size: either 4 or 8; all floating point arrays passed
                       through this interface are expected to have this
                       storage size; so if the 'file_word_size' value is 
                       different, then the data will be converted
    file_word_size: size of floating point data stored in the file (4 or 8)
    exoid (OUT): the integer file descriptor of the new file
*/
const char* exm_create ( const char* filename, int mode,
                         int convert_word_size, int file_word_size,
                         int* exoid )
{
  if ( convert_word_size != 4 && convert_word_size != 8 )
    return "invalid 'convert_word_size' given to exm_create()";
  
  if ( file_word_size != 4 && file_word_size != 8 )
    return "invalid 'file_word_size' given to exm_create()";
  
  *exoid = ex_create( filename, mode, &convert_word_size, &file_word_size );
  
  if ( *exoid < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_open(string filename, int open_mode, int convert_word_size,
           int* file_word_size, float* version, int* exoid)
     
     filename: the string file name of an existing exodus file
     open_mode: either EX_READ=0 or EX_WRITE=1
     convert_word_size: if non-zero, then all floating point arrays passed
                        through this interface are expected to have this
                        storage size (either 4 or 8 bytes);  so if the file
                        has a different size, then the data will be converted
     file_word_size (OUT): 4 if the file stores single precision, 8 if double
     version (OUT): the Exodus version (a float)
     exoid (OUT): the integer file descriptor of the opened file
*/
const char* exm_open ( const char* filename, int mode, int convert_word_size,
                       int* file_word_size, float* version, int* exoid )
{
  int comp_ws, io_ws;
  
  *file_word_size = 0;
  *version = 0.0;  /* just initialize to something */
  
  if ( convert_word_size == 0 )
  {
    /* want to open the file with the same compute word size as the file
       was created to begin with; so try opening in double then check the
       io_ws value;  if they don't agree, then close and use float */
    comp_ws = 8;
    io_ws   = 0;    /* zero here means get the size stored in the file */
    
    *exoid = ex_open( filename, mode, &comp_ws, &io_ws, version );
  
    if ( *exoid < 0 || io_ws != comp_ws )
    {
      if ( *exoid >= 0 ) ex_close( *exoid );
      comp_ws = 4;
      io_ws   = 0;
      *version = 0.0;
      *exoid = ex_open( filename, mode, &comp_ws, &io_ws, version );
    }
    
    if ( *exoid < 0 )
      return exm_get_error_string();
  }
  else if ( convert_word_size == 4 || convert_word_size == 8 )
  {
    comp_ws = convert_word_size;
    io_ws   = 0;    /* zero here means get the size stored in the file */
    
    *exoid = ex_open( filename, mode, &comp_ws, &io_ws, version );
    
    if ( *exoid < 0 )
      return exm_get_error_string();
  }
  else
    return "invalid 'convert_word_size' given to exm_open()";
  
  *file_word_size = io_ws;
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_close(int exoid)
  
     exoid: an integer file descriptor of an open exodus file
*/
const char* exm_close( int exoid )
{
  if ( ex_close( exoid ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_init(int exoid, char* title, int* counts)
  
     'exoid' is an integer file descriptor of an open exodus file
     'title' a char buffer of length MAX_LINE_LENGTH+1 to hold the title
     'counts' an integer buffer of length 17 to hold each count:
         [ 0] = num_dim
         [ 1] = num_nodes
         [ 2] = num_edges
         [ 3] = num_edge_blk
         [ 4] = num_faces
         [ 5] = num_face_blk
         [ 6] = num_elems
         [ 7] = num_elem_blk
         [ 8] = num_node_sets
         [ 9] = num_edge_sets
         [10] = num_face_sets
         [11] = num_side_sets
         [12] = num_elem_sets
         [13] = num_node_maps
         [14] = num_edge_maps
         [15] = num_face_maps
         [16] = num_elem_maps
*/
const char* exm_get_init( int exoid, char* title, int* counts )
{
  ex_init_params ex_params;
  
  if ( ex_get_init_ext( exoid, &ex_params ) >= 0 )
  {
    int i;
    
    strncpy( title, ex_params.title, MAX_LINE_LENGTH );
    title[MAX_LINE_LENGTH] = 0;
    for ( i = strlen(title); i < MAX_LINE_LENGTH; ++i )
      title[i] = 0;
    
    counts[ 0] = ex_params.num_dim;
    counts[ 1] = ex_params.num_nodes;
    counts[ 2] = ex_params.num_edge;
    counts[ 3] = ex_params.num_edge_blk;
    counts[ 4] = ex_params.num_face;
    counts[ 5] = ex_params.num_face_blk;
    counts[ 6] = ex_params.num_elem;
    counts[ 7] = ex_params.num_elem_blk;
    counts[ 8] = ex_params.num_node_sets;
    counts[ 9] = ex_params.num_edge_sets;
    counts[10] = ex_params.num_face_sets;
    counts[11] = ex_params.num_side_sets;
    counts[12] = ex_params.num_elem_sets;
    counts[13] = ex_params.num_node_maps;
    counts[14] = ex_params.num_edge_maps;
    counts[15] = ex_params.num_face_maps;
    counts[16] = ex_params.num_elem_maps;
  }
  else
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_inquire_counts(int exoid, int* counts_array)
  
     exoid: an open exodus file descriptor
     counts_array: an integer buffer of length 41 filled with the following
       [ 0] = number of dimensions
       [ 1] = number of nodes
       [ 2] = number of elements
       [ 3] = number of element blocks
       [ 4] = number of node sets
       [ 5] = length of node set node list
       [ 6] = number of side sets
       [ 7] = length of side set node list
       [ 8] = length of side set element list
       [ 9] = number of QA records
       [10] = number of info records
       [11] = number of time steps in the database
       [12] = number of element block properties
       [13] = number of node set properties
       [14] = number of side set properties
       [15] = length of node set distribution factor list
       [16] = length of side set distribution factor list
       [17] = number of element map properties
       [18] = number of node map properties
       [19] = number of element maps
       [20] = number of node maps
       [21] = number of edges
       [22] = number of edge blocks
       [23] = number of edge sets
       [24] = length of concat edge set edge list
       [25] = length of concat edge set dist factor list
       [26] = number of properties stored per edge block
       [27] = number of properties stored per edge set
       [28] = number of faces
       [29] = number of face blocks
       [30] = number of face sets
       [31] = length of concat face set face list
       [32] = length of concat face set dist factor list
       [33] = number of properties stored per face block
       [34] = number of properties stored per face set
       [35] = number of element sets
       [36] = length of concat element set element list
       [37] = length of concat element set dist factor list
       [38] = number of properties stored per elem set
       [39] = number of edge maps
       [40] = number of face maps
*/
const char* exm_inquire_counts( int exoid, int* counts )
{
  int n;
  float fdum;
  char cdum;
  
#if 0
  Got the inquiry values from the exodusII.h file.  Excluded these:
  
    EX_INQ_FILE_TYPE       /* EXODUS II file type*/
    EX_INQ_API_VERS        /* API version number */
    EX_INQ_DB_VERS         /* database version number */
    EX_INQ_TITLE           /* database title     */
    EX_INQ_LIB_VERS        /* API Lib vers number*/
#endif

#define NUM_INQ_VALS 41
  
  int inq[NUM_INQ_VALS] = {
    EX_INQ_DIM,            /* number of dimensions */
    EX_INQ_NODES,          /* number of nodes    */
    EX_INQ_ELEM,           /* number of elements */
    EX_INQ_ELEM_BLK,       /* number of element blocks */
    EX_INQ_NODE_SETS,      /* number of node sets*/
    EX_INQ_NS_NODE_LEN,    /* length of node set node list */
    EX_INQ_SIDE_SETS,      /* number of side sets*/
    EX_INQ_SS_NODE_LEN,    /* length of side set node list */
    EX_INQ_SS_ELEM_LEN,    /* length of side set element list */
    EX_INQ_QA,             /* number of QA records */
    EX_INQ_INFO,           /* number of info records */
    EX_INQ_TIME,           /* number of time steps in the database */
    EX_INQ_EB_PROP,        /* number of element block properties */
    EX_INQ_NS_PROP,        /* number of node set properties */
    EX_INQ_SS_PROP,        /* number of side set properties */
    EX_INQ_NS_DF_LEN,      /* length of node set distribution factor list*/
    EX_INQ_SS_DF_LEN,      /* length of side set distribution factor list*/
    EX_INQ_EM_PROP,        /* number of element map properties */
    EX_INQ_NM_PROP,        /* number of node map properties */
    EX_INQ_ELEM_MAP,       /* number of element maps */
    EX_INQ_NODE_MAP,       /* number of node maps*/
    EX_INQ_EDGE,           /* number of edges    */
    EX_INQ_EDGE_BLK,       /* number of edge blocks */
    EX_INQ_EDGE_SETS,      /* number of edge sets   */
    EX_INQ_ES_LEN,         /* length of concat edge set edge list       */
    EX_INQ_ES_DF_LEN,      /* length of concat edge set dist factor list*/
    EX_INQ_EDGE_PROP,      /* number of properties stored per edge block    */
    EX_INQ_ES_PROP,        /* number of properties stored per edge set      */
    EX_INQ_FACE,           /* number of faces */
    EX_INQ_FACE_BLK,       /* number of face blocks */
    EX_INQ_FACE_SETS,      /* number of face sets */
    EX_INQ_FS_LEN,         /* length of concat face set face list */
    EX_INQ_FS_DF_LEN,      /* length of concat face set dist factor list*/
    EX_INQ_FACE_PROP,      /* number of properties stored per face block */
    EX_INQ_FS_PROP,        /* number of properties stored per face set */
    EX_INQ_ELEM_SETS,      /* number of element sets */
    EX_INQ_ELS_LEN,        /* length of concat element set element list     */
    EX_INQ_ELS_DF_LEN,     /* length of concat element set dist factor list */
    EX_INQ_ELS_PROP,       /* number of properties stored per elem set      */
    EX_INQ_EDGE_MAP,       /* number of edge maps                     */
    EX_INQ_FACE_MAP        /* number of face maps                     */
  };
  
  int i;
  
  for ( i = 0; i < NUM_INQ_VALS; ++i )
  {
    if ( ex_inquire( exoid, inq[i], &n, &fdum, &cdum ) < 0 )
      return exm_get_error_string();
    
    counts[i] = n;
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_info(int exoid, int num_info, char* info)
  
     exoid: an open exodus file descriptor
     num_info: the number of info records in the file
     info: a char buffer of size num_info*(MAX_LINE_LENGTH+1) where each
           line is sequential and uses MAX_LINE_LENGTH+1 characters and
           is padded with null characters
*/
const char* exm_get_info( int exoid, int num_info, char* info )
{
  if ( num_info > 0 )
  {
    char** infop;
    int i, k, ierr;
    
    infop = (char**) malloc( num_info*sizeof(char*) );
    for ( i = 0; i < num_info; ++i )
      infop[i] = info + i*(MAX_LINE_LENGTH+1);
    
    ierr = ex_get_info( exoid, infop );
    
    if ( ierr < 0 ) {
      free( infop );
      return exm_get_error_string();
    }
    
    for ( i = 0; i < num_info; ++i ) {
      for ( k = strlen( infop[i] ); k <=MAX_LINE_LENGTH; ++k )
        infop[i][k] = 0;
    }
    
    free( infop );
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_ids(int exoid, int idtype, int* ids)
  
     exoid: an open exodus file descriptor
     idtype: one of EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK, EX_NODE_SET
             EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET, EX_NODE_MAP
             EX_EDGE_MAP, EX_FACE_MAP, or EX_ELEM_MAP
     ids: an integer buffer with length large enough to store the ids
*/
const char* exm_get_ids( int exoid, int idtype, int* ids )
{
  int ierr;
  
  if ( idtype == EX_EDGE_BLOCK )
    ierr = ex_get_ids( exoid, EX_EDGE_BLOCK, ids );
  else if ( idtype == EX_FACE_BLOCK )
    ierr = ex_get_ids( exoid, EX_FACE_BLOCK, ids );
  else if ( idtype == EX_ELEM_BLOCK )
    ierr = ex_get_ids( exoid, EX_ELEM_BLOCK, ids );
  else if ( idtype == EX_NODE_SET )
    ierr = ex_get_ids( exoid, EX_NODE_SET, ids );
  else if ( idtype == EX_EDGE_SET )
    ierr = ex_get_ids( exoid, EX_EDGE_SET, ids );
  else if ( idtype == EX_FACE_SET )
    ierr = ex_get_ids( exoid, EX_FACE_SET, ids );
  else if ( idtype == EX_ELEM_SET )
    ierr = ex_get_ids( exoid, EX_ELEM_SET, ids );
  else if ( idtype == EX_SIDE_SET )
    ierr = ex_get_ids( exoid, EX_SIDE_SET, ids );
  else if ( idtype == EX_NODE_MAP )
    ierr = ex_get_ids( exoid, EX_NODE_MAP, ids );
  else if ( idtype == EX_EDGE_MAP )
    ierr = ex_get_ids( exoid, EX_EDGE_MAP, ids );
  else if ( idtype == EX_FACE_MAP )
    ierr = ex_get_ids( exoid, EX_FACE_MAP, ids );
  else if ( idtype == EX_ELEM_MAP )
    ierr = ex_get_ids( exoid, EX_ELEM_MAP, ids );
  else
    return "invalid id type given to exm_get_ids()";
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_block(int exoid, int block_type, int block_id,
                char* type_name, int* counts)
  
     exoid: an open exodus file descriptor
     block_type: one of EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK
     block_id: integer block id
     type_name: a char buffer to store the type of objects in the block, such
                as 'HEX'; must have length MAX_STR_LENGTH+1
     counts: an integer buffer of length 5
               [0] = num objects in the block
               [1] = num nodes per object
               [2] = num edges per object
               [3] = num faces per object
               [4] = num attributes per object
*/
const char* exm_get_block( int exoid, int btype, int bid,
                           char* tname, int* counts )
{
  int i, ierr;
  
  if ( btype == EX_EDGE_BLOCK ) {
    ierr = ex_get_block( exoid, EX_EDGE_BLOCK, bid, tname,
                         counts, counts+1, NULL, NULL, counts+4 );
    counts[2] = counts[3] = 0; /* num edges & faces per object always zero */
  }
  else if ( btype == EX_FACE_BLOCK ) {
    ierr = ex_get_block( exoid, EX_FACE_BLOCK, bid, tname,
                         counts, counts+1, NULL, NULL, counts+4 );
    counts[2] = counts[3] = 0; /* num edges & faces per object always zero */
  }
  else if ( btype == EX_ELEM_BLOCK )
    ierr = ex_get_block( exoid, EX_ELEM_BLOCK, bid, tname,
                         counts, counts+1, counts+2, counts+3, counts+4 );
  else
    return "invalid block type given to exm_get_block()";
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  tname[MAX_STR_LENGTH] = 0;
  for ( i = strlen(tname); i < MAX_STR_LENGTH; ++i )
    tname[i] = 0;
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_set_param(int exoid, int set_type, int set_id,
                    int* num_objs, int* num_dist_factors)
  
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,
               EX_SIDE_SET
     set_id: integer set id
     num_objs (OUT): number of objects in the set
     num_dist_factors (OUT): number of distribution factors
*/
const char* exm_get_set_param( int exoid, int stype, int sid,
                               int* nume, int* numdf )
{
  int ierr;
  
  if ( stype == EX_NODE_SET )
    ierr = ex_get_set_param( exoid, EX_NODE_SET, sid, nume, numdf );
  else if ( stype == EX_EDGE_SET )
    ierr = ex_get_set_param( exoid, EX_EDGE_SET, sid, nume, numdf );
  else if ( stype == EX_FACE_SET )
    ierr = ex_get_set_param( exoid, EX_FACE_SET, sid, nume, numdf );
  else if ( stype == EX_ELEM_SET )
    ierr = ex_get_set_param( exoid, EX_ELEM_SET, sid, nume, numdf );
  else if ( stype == EX_SIDE_SET )
    ierr = ex_get_set_param( exoid, EX_SIDE_SET, sid, nume, numdf );
  else
    return "invalid set type given to exm_get_set_param()";
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  return NULL;
}

int exm_helper_get_qa_8( int exoid, int nrec, char* qabuf )
{
  char* qarec[8][4];
  int i, j, k;
  int ierr;
  
  for ( i = 0; i < nrec; ++i )
    for ( j = 0; j < 4; ++j )
      qarec[i][j] = qabuf + i*4*(MAX_STR_LENGTH+1) + j*(MAX_STR_LENGTH+1);
  
  ierr = ex_get_qa( exoid, qarec );
  
  if ( ierr >= 0 )
  {
    for ( i = 0; i < nrec; ++i ) {
      for ( j = 0; j < 4; ++j ) {
        qarec[i][j][MAX_STR_LENGTH] = 0;
        for ( k = strlen( qarec[i][j] ); k < MAX_STR_LENGTH; ++k )
          qarec[i][j][k] = 0;
      }
    }
  }
  
  return ierr;
}

#define MAX_QA_RECORDS 1024

struct exm_helper_QA_struct
{
  char* qarec[MAX_QA_RECORDS][4];
};

int exm_helper_get_qa_alloc( int exoid, int nrec, char* qabuf )
{
  struct exm_helper_QA_struct * qastruct;
  int i, j, k;
  int ierr;
  
  qastruct = (struct exm_helper_QA_struct *)
                            malloc( sizeof(struct exm_helper_QA_struct) );
  
  for ( i = 0; i < nrec; ++i )
    for ( j = 0; j < 4; ++j )
      (qastruct->qarec)[i][j] =
                   qabuf + i*4*(MAX_STR_LENGTH+1) + j*(MAX_STR_LENGTH+1);
  
  ierr = ex_get_qa( exoid, qastruct->qarec );
  
  if ( ierr >= 0 )
  {
    for ( i = 0; i < nrec; ++i ) {
      for ( j = 0; j < 4; ++j ) {
        (qastruct->qarec)[i][j][MAX_STR_LENGTH] = 0;
        for ( k = strlen( (qastruct->qarec)[i][j] ); k < MAX_STR_LENGTH; ++k )
          (qastruct->qarec)[i][j][k] = 0;
      }
    }
  }
  
  free( qastruct );
  
  return ierr;
}

/*
GENMOD: DOC:
  exm_get_qa(int exoid, int num_qa, char* qa_records)
  
     exoid: an open exodus file descriptor
     num_qa: the number of QA records stored in the file
     qa_records: a char buffer with length 4*num_qa*(MAX_STR_LENGTH+1);
                 so that each record has 4 sequential entries each of length
                 MAX_STR_LENGTH+1 and the records are stored sequentially
*/
const char* exm_get_qa( int exoid, int num_qa, char* qabuf )
{
  if ( num_qa > 0 )
  {
    int ierr;
    
    if ( num_qa <= 8 )
      ierr = exm_helper_get_qa_8( exoid, num_qa, qabuf );
    else if ( num_qa < MAX_QA_RECORDS )
      ierr = exm_helper_get_qa_alloc( exoid, num_qa, qabuf );
    else
      return "maximum number of QA records exceeded for exomod.c";
    if ( ierr < 0 )
      return exm_get_error_string();
  }
  else if ( num_qa < 0 )
    return "argument 'num_qa' was negative sent into exm_get_qa()";
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_all_times(int exoid, REAL* times)
  
     exoid: an open exodus file descriptor
     times: a floating point buffer of length equal to the number of time
            values; if the file stores doubles, then the buffer must store
            doubles, otherwise floats
*/
const char* exm_get_all_times( int exoid, void* times )
{
  if ( ex_get_all_times( exoid, times ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_var_params(int exoid, int* counts)
  
     exoid: an open exodus file descriptor
     counts: an integer buffer of length 10 to store the number of variables
             of each type:
               [0] = num global vars,
               [1] = num node vars,
               [2] = num edge vars,
               [3] = num face vars,
               [4] = num element vars,
               [5] = num nodeset vars,
               [6] = num edgeset vars,
               [7] = num faceset vars,
               [8] = num element set vars,
               [9] = num sideset vars
*/
const char* exm_get_var_params( int exoid, int* counts )
{
  int i;
  
  ex_entity_type t[10] = { EX_GLOBAL,
                           EX_NODAL,
                           EX_EDGE_BLOCK,
                           EX_FACE_BLOCK,
                           EX_ELEM_BLOCK,
                           EX_NODE_SET,
                           EX_EDGE_SET,
                           EX_FACE_SET,
                           EX_ELEM_SET,
                           EX_SIDE_SET };
  
  for ( i = 0; i < 10; ++i ) {
    if ( ex_get_variable_param( exoid, t[i], counts+i ) < 0 )
      return exm_get_error_string();
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_all_var_names(int exoid,  char* global,  char* node, char* edge,
                        char* face, char* element, char* nodeset,
                        char* edgeset, char* faceset, char* elemset,
                        char* sideset )
  
     exoid: an open exodus file descriptor
     the rest are char buffers to hold the variable names for each var type;
     each must have length MAX_STR_LENGTH+1 times the number of variables
     of that type; they get filled with the names and padded on the right
     with NUL chars
*/
const char* exm_get_all_var_names( int exoid, char* global,  char* node,
                                   char* edge,    char* face,
                                   char* element, char* nodeset,
                                   char* edgeset, char* faceset,
                                   char* elemset, char* sideset )
{
  int i, maxcnt;
  int cnt[10];
  
  ex_entity_type t[10] = { EX_GLOBAL,
                           EX_NODAL,
                           EX_EDGE_BLOCK,
                           EX_FACE_BLOCK,
                           EX_ELEM_BLOCK,
                           EX_NODE_SET,
                           EX_EDGE_SET,
                           EX_FACE_SET,
                           EX_ELEM_SET,
                           EX_SIDE_SET };
  
  char* cp[10] = { global,
                   node,
                   edge,
                   face,
                   element,
                   nodeset,
                   edgeset,
                   faceset,
                   elemset,
                   sideset };
  
  /* load the variable counts and get the max number of names */
  maxcnt = 0;
  for ( i = 0; i < 10; ++i )
  {
    if ( ex_get_variable_param( exoid, t[i], cnt+i ) < 0 )
      return exm_get_error_string();
    
    if ( maxcnt < cnt[i] )
      maxcnt = cnt[i];
  }
  
  if ( maxcnt > 0 )
  {
    int j;
    char** names;
    
    names = (char**)malloc( maxcnt*sizeof(char*) );
    
    for ( i = 0; i < 10; ++i )
    {
      if ( cnt[i] > 0 )
      {
        for ( j = 0; j < cnt[i]; ++j )
          names[j] = cp[i] + (MAX_STR_LENGTH+1)*j;
        
        if ( ex_get_variable_names( exoid, t[i], cnt[i], names ) < 0 ) {
          free(names);
          return exm_get_error_string();
        }
        
        /* pad each name with NUL chars on the right */
        int k;
        for ( j = 0; j < cnt[i]; ++j ) {
          for ( k = strlen( names[j] ); k <= MAX_STR_LENGTH; ++k )
            names[j][k] = 0;
        }
      }
    }
    
    free(names);
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_truth_table(int exoid, int var_type, int num_blocks,
                      int num_vars, int* table )
  
     exoid: an open exodus file descriptor
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     num_blocks: the number of blocks or sets stored for the var_type
     num_vars: the number of variables stored for the var_type
     table: an integer buffer of length num_blocks*num_vars to recieve the
            truth table values
*/
const char* exm_get_truth_table( int exoid, int var_type, int nblocks,
                                 int nvars, int* table )
{
  ex_entity_type t;
  
  if      ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
  else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
  else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
  else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
  else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
  else
    return "invalid variable type given to exm_get_truth_table()";
  
  if ( nblocks > 0 && nvars > 0 ) {
    if ( ex_get_truth_table( exoid, t, nblocks, nvars, table ) < 0 )
      return exm_get_error_string();
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_coord_names(int exoid, int ndim, char* names)
  
     exoid: an open exodus file descriptor
     ndim: the spatial dimension stored in the file
     names: char buffer to store the coordinate names;  must have length
            ndim*(MAX_STR_LENGTH+1); the name for the X coordinate is stored
            in the first MAX_STR_LENGTH+1 characters, then Y then Z.
            If the names are not stored in the file, then the string
            "_not_stored_" will be placed in the names buffer
*/
const char* exm_get_coord_names( int exoid, int ndim, char* names )
{
  int ierr;
  char* coordnames[3] = { 0, 0, 0 };
  
  if ( ndim > 0 && ndim <= 3 )
  {
    coordnames[0] = names;
    if ( ndim > 1 ) coordnames[1] = names + (MAX_STR_LENGTH+1);
    if ( ndim > 2 ) coordnames[2] = names + 2*(MAX_STR_LENGTH+1);
    
    ierr = ex_get_coord_names( exoid, coordnames );
    
    if ( ierr == 0 )
    {
      int i, k;
      for ( i = 0; i < ndim; ++i ) {
        coordnames[i][MAX_STR_LENGTH] = 0;
        for ( k = strlen( coordnames[i] ); k < MAX_STR_LENGTH; ++k )
          coordnames[i][k] = 0;
      }
    }
    else if ( ierr > 0 )
    {
      /* probably not stored */
      strcpy( names, "_not_stored_" );
    }
    else
      return exm_get_error_string();
  }
  else
    return "invalid spatial dimension given to exm_get_coord_names()";
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_coord(int exoid, REAL* xbuf, REAL* ybuf, REAL* zbuf)
  
     exoid: an open exodus file descriptor
     xbuf, ybuf, zbuf: buffers for the X-, Y-, and Z-coordinates; the ybuf is
                       only used if the spatial dimension is 2 or 3; zbuf only
                       if dim is 3; if the file stores doubles, then the
                       buffers must store doubles as well, otherwise floats
*/
const char* exm_get_coord( int exoid, void* xbuf, void* ybuf, void* zbuf )
{
  if ( ex_get_coord( exoid, xbuf, ybuf, zbuf ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_conn(int exoid, int block_type, int block_id, int conn_type,
               int* conn)
  
     exoid: an open exodus file descriptor
     block_type: one of  EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK
     block_id: the target block id
     conn_type: type of connections (one of EX_NODE, EX_EDGE, EX_FACE)
     conn: an integer buffer to store the connectivity matrix; the length
           must be num_objects*num_connections_per_object (such as
           num_elements*num_nodes_per_element)
*/
const char* exm_get_conn( int exoid, int block_type, int block_id,
                          int conn_type, int* conn )
{
  ex_entity_type t;
  int *nc, *gc, *fc;
  
  if      ( block_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( block_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( block_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else
    return "invalid block type given to exm_get_conn()";
  
  nc = gc = fc = NULL;
  
  if      ( conn_type == 15 ) nc = conn;  /* node */
  else if ( conn_type == 16 ) gc = conn;  /* edge */
  else if ( conn_type == 17 ) fc = conn;  /* face */
  else
    return "invalid connectivity type given to exm_get_conn()";
  
  if ( ex_get_conn( exoid, t, block_id, nc, gc, fc ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_set(int exoid, int set_type, int set_id,
              int* set_values, int* auxiliary)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     set_values: the set values; length is the number of objects in the set
     auxiliary: unused for EX_NODE_SET and EX_ELEM_SET; must have same length
                as 'set_values' otherwise; stores +/- orientations for
                EX_EDGE_SET and EX_FACE_SET, or local side numbers for
                EX_SIDE_SET
*/
const char* exm_get_set( int exoid, int set_type, int set_id,
                         int* set_values, int* auxiliary )
{
  ex_entity_type st;
  
  st = EX_NODE_SET;
  if      ( set_type == EX_NODE_SET ) { st = EX_NODE_SET; auxiliary = NULL; }
  else if ( set_type == EX_EDGE_SET ) { st = EX_EDGE_SET; }
  else if ( set_type == EX_FACE_SET ) { st = EX_FACE_SET; }
  else if ( set_type == EX_SIDE_SET ) { st = EX_SIDE_SET; }
  else if ( set_type == EX_ELEM_SET ) { st = EX_ELEM_SET; auxiliary = NULL; }
  else
    return "invalid set type given to exm_get_set()";
  
  if ( ex_get_set( exoid, st, set_id, set_values, auxiliary ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_set_dist_fact(int exoid, int set_type, int set_id, REAL* values)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     values: the distribution factors; length is the number of objects in the
             set; the type is float if the file stores float, otherwise double
*/
const char* exm_get_set_dist_fact( int exoid, int set_type, int set_id,
                                   void * values )
{
  ex_entity_type st;
  
  st = EX_NODE_SET;
  if      ( set_type == EX_NODE_SET ) st = EX_NODE_SET;
  else if ( set_type == EX_EDGE_SET ) st = EX_EDGE_SET;
  else if ( set_type == EX_FACE_SET ) st = EX_FACE_SET;
  else if ( set_type == EX_SIDE_SET ) st = EX_SIDE_SET;
  else if ( set_type == EX_ELEM_SET ) st = EX_ELEM_SET;
  else
    return "invalid set type given to exm_get_set_dist_fact()";
  
  if ( ex_get_set_dist_fact( exoid, st, set_id, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_map(int exoid, int map_type, int map_id, int* map_values)
     
     exoid: an open exodus file descriptor
     map_type: one of EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP
     map_id: the target map id
     map_values: the map values; length is the number of objects in the map
*/
const char* exm_get_map( int exoid, int map_type, int map_id, int* map_values )
{
  ex_entity_type mt;
  int ierr;
  
  if      ( map_type == EX_NODE_MAP ) { mt = EX_NODE_MAP; }
  else if ( map_type == EX_EDGE_MAP ) { mt = EX_EDGE_MAP; }
  else if ( map_type == EX_FACE_MAP ) { mt = EX_FACE_MAP; }
  else if ( map_type == EX_ELEM_MAP ) { mt = EX_ELEM_MAP; }
  else
    return "invalid map type given to exm_get_map()";
  
  ierr = 0;
  if ( map_id < 0 )
  {
    if ( mt == EX_NODE_MAP )
      ierr = ex_get_node_num_map( exoid, map_values );
    else if ( mt == EX_EDGE_MAP )
      ierr = ex_get_id_map( exoid, EX_EDGE_MAP, map_values );
    else if ( mt == EX_FACE_MAP )
      ierr = ex_get_id_map( exoid, EX_FACE_MAP, map_values );
    else
      ierr = ex_get_elem_num_map( exoid, map_values );
  }
  else
    ierr = ex_get_num_map( exoid, mt, map_id, map_values );
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_glob_vars(int exoid, int time_step, int num_global_vars, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     num_global_vars: the number of global variables in the file
     values: the variable values; length must be 'num_global_vars'; the type
             is float if the file stores float, otherwise double
*/
const char* exm_get_glob_vars( int exoid, int time_step,
                               int num_global_vars, void* values )
{
  if ( ex_get_glob_vars( exoid, time_step, num_global_vars, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_nodal_var(int exoid, int time_step, int var_idx,
                    int num_nodes, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_idx: the variable index
     num_nodes: the number of nodes in the file
     values: the variable values; length must be 'num_nodes'; the type is
             float if the file stores float, otherwise double
*/
const char* exm_get_nodal_var( int exoid, int time_step, int var_idx,
                               int num_nodes, void* values )
{
  if ( ex_get_nodal_var( exoid, time_step, var_idx, num_nodes, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_var(int exoid, int time_step, int var_type, int var_idx,
              int block_id, int num_objects, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     block_id: the id of the block or set
     num_objects: the number of objects in the block or set
     values: the variable values; length must be 'num_objects'; the type is
             float if the file stores float, otherwise double
*/
const char* exm_get_var( int exoid, int time_step, int var_type,
                         int var_idx, int block_id, int num_objects,
                         void* values )
{
  ex_entity_type t;
  
  if      ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
  else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
  else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
  else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
  else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
  else
    return "invalid variable type given to exm_get_var()";
  
  if ( ex_get_var( exoid, time_step, t, var_idx,
                   block_id, num_objects, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_block_var(int exoid, int time_step, int var_type,
                    int var_idx, int num_ids, const int* block_ids,
                    const int* num_objects, const int* is_stored,
                    char storage, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     num_ids: the number of block or set ids
     block_id: length 'num_ids'; the ids of each block or set
     num_objects: length 'num_ids'; the number of objects in each block or set
     is_stored: length 'num_ids'; the truth table (true if the variable is
                stored in a given block id, false otherwise)
     storage: 'f' if the file stores floats, otherwise 'd' for double
     values: the variable values; length must be the sum of the entries in
             the 'num_objects' array; the type is float if the file stores
             float, otherwise double
*/
const char* exm_get_block_var( int exoid, int time_step, int var_type,
                               int var_idx, int num_ids, const int* block_ids,
                               const int* num_objects, const int* is_stored,
                               char storage, void* values )
{
  if ( num_ids > 0 )
  {
    int b, i;
    ex_entity_type t;
    
    if      ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
    else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
    else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
    else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
    else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
    else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
    else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
    else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
    else
      return "invalid variable type given to exm_get_block_var()";
    
    for ( b = 0; b < num_ids; ++b )
    {
      if ( is_stored[b] )
      {
        if ( ex_get_var( exoid, time_step, t, var_idx,
                         block_ids[b], num_objects[b], values ) < 0 )
          return exm_get_error_string();
      }
      else if ( storage == 'f' )
      {
        float * fvals;
        fvals = (float*)values;
        for ( i = 0; i < num_objects[b]; ++i )
          fvals[i] = 0.0;
      }
      else
      {
        double * dvals;
        dvals = (double*)values;
        for ( i = 0; i < num_objects[b]; ++i )
          dvals[i] = 0.0;
      }
      
      if ( storage == 'f' )
        values = (void*)( ((float*)values) + num_objects[b] );
      else
        values = (void*)( ((double*)values) + num_objects[b] );
    }
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_get_var_time(int exoid, int var_type, int var_idx, int obj_index,
                   int beg_time_step, int end_time_step, REAL* values)
     
     exoid: an open exodus file descriptor
     var_type: one of EX_GLOBAL, EX_NODE, EX_ELEM_BLOCK, EX_EDGE_BLOCK,
               EX_FACE_BLOCK, EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     obj_index: the 0-offset index of the desired object (the internal index)
     beg_time_step: staring time step number (time steps start at 1)
     end_time_step: ending time step number
     values: the variable values; length must be end_time_step-beg_time_step+1;
             the type is float if the file stores float, otherwise double
*/
const char* exm_get_var_time( int exoid, int var_type, int var_idx,
                              int obj_index,
                              int beg_time_step, int end_time_step,
                              void* values )
{
  ex_entity_type t;
  
  if      ( var_type == EX_GLOBAL     ) t = EX_GLOBAL;
  else if ( var_type == 15            ) t = EX_NODAL;
  else if ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
  else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
  else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
  else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
  else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
  else
    return "invalid variable type given to exm_get_var_time()";
  
  if ( ex_get_var_time( exoid, t, var_idx, obj_index,
                        beg_time_step, end_time_step, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*****************************************************************************/

/*
GENMOD: DOC:
  exm_put_init(int exoid, string title, int* counts)
  
     'exoid' is an integer file descriptor of an open exodus file
     'title' is the title string (only MAX_LINE_LENGTH characters are written)
     'counts' an integer buffer of length 17 containing each count:
         [ 0] = num_dim
         [ 1] = num_nodes
         [ 2] = num_edges
         [ 3] = num_edge_blk
         [ 4] = num_faces
         [ 5] = num_face_blk
         [ 6] = num_elems
         [ 7] = num_elem_blk
         [ 8] = num_node_sets
         [ 9] = num_edge_sets
         [10] = num_face_sets
         [11] = num_side_sets
         [12] = num_elem_sets
         [13] = num_node_maps
         [14] = num_edge_maps
         [15] = num_face_maps
         [16] = num_elem_maps
*/
const char* exm_put_init( int exoid, const char* title, const int* counts )
{
  ex_init_params ex_params;
  
  strncpy( ex_params.title, title, MAX_LINE_LENGTH );
  ex_params.title[MAX_LINE_LENGTH] = 0;
  
  ex_params.num_dim       = counts[ 0];
  ex_params.num_nodes     = counts[ 1];
  ex_params.num_edge      = counts[ 2];
  ex_params.num_edge_blk  = counts[ 3];
  ex_params.num_face      = counts[ 4];
  ex_params.num_face_blk  = counts[ 5];
  ex_params.num_elem      = counts[ 6];
  ex_params.num_elem_blk  = counts[ 7];
  ex_params.num_node_sets = counts[ 8];
  ex_params.num_edge_sets = counts[ 9];
  ex_params.num_face_sets = counts[10];
  ex_params.num_side_sets = counts[11];
  ex_params.num_elem_sets = counts[12];
  ex_params.num_node_maps = counts[13];
  ex_params.num_edge_maps = counts[14];
  ex_params.num_face_maps = counts[15];
  ex_params.num_elem_maps = counts[16];
  
  if ( ex_put_init_ext( exoid, &ex_params ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

int exm_helper_put_qa_8( int exoid, int nrec, char* qabuf )
{
  char* qarec[8][4];
  int i, j;
  int slen;
  
  for ( i = 0; i < nrec; ++i )
    for ( j = 0; j < 4; ++j )
    {
      qarec[i][j] = qabuf;
      slen = strlen( qabuf );
      if ( slen > MAX_STR_LENGTH )
        qabuf[MAX_STR_LENGTH] = 0;
      qabuf += (slen+1);
    }
  
  return ex_put_qa( exoid, nrec, qarec );
}

int exm_helper_put_qa_alloc( int exoid, int nrec, char* qabuf )
{
  struct exm_helper_QA_struct * qastruct;
  int i, j;
  int slen;
  int ierr;
  
  qastruct = (struct exm_helper_QA_struct *)
                            malloc( sizeof(struct exm_helper_QA_struct) );
  
  for ( i = 0; i < nrec; ++i )
    for ( j = 0; j < 4; ++j )
    {
      (qastruct->qarec)[i][j] = qabuf;
      slen = strlen( qabuf );
      if ( slen > MAX_STR_LENGTH )
        qabuf[MAX_STR_LENGTH] = 0;
      qabuf += (slen+1);
    }
  
  ierr = ex_put_qa( exoid, nrec, qastruct->qarec );
  
  free( qastruct );
  
  return ierr;
}

/*
GENMOD: ARGIN: qabuf
GENMOD: DOC:
  exm_put_qa(int exoid, int num_qa, char* qabuf)
  
     exoid: an open exodus file descriptor
     num_qa: the number of QA records to store
     qabuf: a char buffer containing the QA records;  there must be
            4*num_qa null terminated strings concatenated together
*/
const char* exm_put_qa( int exoid, int num_qa, char* qabuf )
{
  if ( num_qa < 0 )
    return "argument 'num_qa' was negative sent into exm_put_qa()";
  else
  {
    int ierr;
    
    if ( num_qa <= 8 )
      ierr = exm_helper_put_qa_8( exoid, num_qa, qabuf );
    else if ( num_qa < MAX_QA_RECORDS )
      ierr = exm_helper_put_qa_alloc( exoid, num_qa, qabuf );
    else
      return "maximum number of QA records exceeded for exomod.c";
    if ( ierr < 0 )
      return exm_get_error_string();
  }
  
  return NULL;
}


/*
GENMOD: ARGIN: info
GENMOD: DOC:
  exm_put_info(int exoid, int num_info, char* info)
  
     exoid: an open exodus file descriptor
     num_info: the number of info records in the file
     info: a char buffer containing the QA records;  there must be
            num_info null terminated strings concatenated together
*/
const char* exm_put_info( int exoid, int num_info, char* info )
{
  if ( num_info < 0 )
    return "argument 'num_info' was negative sent into exm_put_info()";
  else
  {
    char** lines;
    int i, slen, ierr;
    
    lines = NULL;
    if ( num_info > 0 )
      lines = (char**) malloc( num_info*sizeof(char*) );
    
    
    for ( i = 0; i < num_info; ++i )
    {
      lines[i] = info;
      slen = strlen(info);
      if ( slen > MAX_LINE_LENGTH )
        info[MAX_LINE_LENGTH] = 0;
      info += (slen+1);
    }
    
    ierr = ex_put_info( exoid, num_info, lines );
    
    if ( num_info > 0 )
      free( lines );
    
    if ( ierr < 0 )
      return exm_get_error_string();
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_coord_names(int exoid, int ndim, const char* xname,
                      const char* yname, const char* zname)
  
     exoid: an open exodus file descriptor
     ndim: the spatial dimension stored in the file
     xname, yname, zname: char buffers containing the coordinate names;  only
                          xname used if dim is one, xname and yname if dim is
                          two, and all three if dim is three
*/
const char* exm_put_coord_names( int exoid, int ndim, const char* xname,
                                 const char* yname, const char* zname )
{
  if ( ndim > 0 && ndim <= 3 )
  {
    const char* coordnames[3] = { 0, 0, 0 };
    coordnames[0] = xname;
    if ( strlen( coordnames[0] ) > MAX_STR_LENGTH )
      return "X coordinate name longer than MAX_STR_LENGTH, "
             "in exm_put_coord_names";
    if ( ndim > 1 ) {
      coordnames[1] = yname;
      if ( strlen( coordnames[1] ) > MAX_STR_LENGTH )
        return "Y coordinate name longer than MAX_STR_LENGTH, "
               "in exm_put_coord_names";
    }
    if ( ndim > 2 ) {
      coordnames[2] = zname;
      if ( strlen( coordnames[2] ) > MAX_STR_LENGTH )
        return "Z coordinate name longer than MAX_STR_LENGTH, "
               "in exm_put_coord_names";
    }
    
    if ( ex_put_coord_names( exoid, (char**)coordnames ) < 0 )
      return exm_get_error_string();
  }
  else
    return "invalid spatial dimension given to exm_put_coord_names()";
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_coord(int exoid, REAL* xbuf, REAL* ybuf, REAL* zbuf)
  
     exoid: an open exodus file descriptor
     xbuf, ybuf, zbuf: buffers for the X-, Y-, and Z-coordinates; the ybuf is
                       only used if the spatial dimension is 2 or 3; zbuf only
                       if dim is 3; if the file stores doubles, then the
                       buffers must store doubles as well, otherwise floats
*/
const char* exm_put_coord( int exoid, const void* xbuf, const void* ybuf,
                                      const void* zbuf )
{
  if ( ex_put_coord( exoid, xbuf, ybuf, zbuf ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_block(int exoid, int block_type, int block_id,
                const char* block_type_name, int num_objects,
                int num_nodes_per_object, int num_edges_per_object,
                int num_faces_per_object, int num_attrs_per_object)
  
     exoid: an open exodus file descriptor
     block_type:  one of EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK
     block_id:  the integer block id
     block_type_name:  a string describing the object types (such as HEX8)
     num_objects:  number of objects/entries in this block
     num_nodes_per_object:  local number of nodes per object
     num_edges_per_object:  local number of edges per object
     num_faces_per_object:  local number of faces per object
     num_attrs_per_object:  number of attributes for each object
*/
const char* exm_put_block( int exoid, int block_type, int block_id,
                           const char* block_type_name, int num_objects,
                           int num_nodes_per_object, int num_edges_per_object,
                           int num_faces_per_object, int num_attrs_per_object )
{
  if ( block_type != EX_ELEM_BLOCK &&
       block_type != EX_EDGE_BLOCK &&
       block_type != EX_FACE_BLOCK )
    return "invalid 'block_type' given to exm_put_block()";
  
  if ( ex_put_block( exoid, block_type, block_id, block_type_name,
                     num_objects, num_nodes_per_object, num_edges_per_object,
                     num_faces_per_object, num_attrs_per_object ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_conn(int exoid, int block_type, int block_id,
               int nodes_per_obj, int edges_per_obj, int faces_per_obj,
               const int* node_conn, const int* edge_conn,
               const int* face_conn)
  
     exoid: an open exodus file descriptor
     block_type: one of  EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK
     block_id: the target block id
     nodes_per_obj: number of local nodes per object
     edges_per_obj: number of local edges per object
     faces_per_obj: number of local faces per object
     node_conn: an integer buffer to store the node connectivity matrix;
                the length must be num_objects*nodes_per_object
                (such as num_elements*num_nodes_per_element)
     edge_conn: an integer buffer to store the edge connectivity matrix;
                the length must be num_objects*edges_per_object
     face_conn: an integer buffer to store the face connectivity matrix;
                the length must be num_objects*faces_per_object
*/
const char* exm_put_conn( int exoid, int block_type, int block_id,
                          int nodes_per_obj, int edges_per_obj,
                          int faces_per_obj,
                          const int* node_conn, const int* edge_conn,
                          const int* face_conn )
{
  ex_entity_type t;
  const int *gc, *fc;
  int ierr;
  
  if      ( block_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( block_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( block_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else
    return "invalid block type given to exm_put_conn()";
  
  gc = fc = NULL;
  if ( edges_per_obj > 0 ) gc = edge_conn;
  if ( faces_per_obj > 0 ) fc = face_conn;
  
  if ( t == EX_ELEM_BLOCK && gc == NULL && fc == NULL )
    ierr = ex_put_elem_conn( exoid, block_id, node_conn );
  else
    ierr = ex_put_conn( exoid, t, block_id, node_conn, gc, fc );
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_set_param(int exoid, int set_type, int set_id,
                    int num_objs, int num_dist_factors)
  
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,
               EX_SIDE_SET
     set_id: integer set id
     num_objs: number of objects in the set
     num_dist_factors: number of distribution factors
*/
const char* exm_put_set_param( int exoid, int stype, int sid,
                               int numobjs, int numdf )
{
  int ierr;
  
  ierr = 0;
  if ( stype == EX_NODE_SET )
    ierr = ex_put_set_param( exoid, EX_NODE_SET, sid, numobjs, numdf );
  else if ( stype == EX_EDGE_SET )
    ierr = ex_put_set_param( exoid, EX_EDGE_SET, sid, numobjs, numdf );
  else if ( stype == EX_FACE_SET )
    ierr = ex_put_set_param( exoid, EX_FACE_SET, sid, numobjs, numdf );
  else if ( stype == EX_ELEM_SET )
    ierr = ex_put_set_param( exoid, EX_ELEM_SET, sid, numobjs, numdf );
  else if ( stype == EX_SIDE_SET )
    ierr = ex_put_set_param( exoid, EX_SIDE_SET, sid, numobjs, numdf );
  else
    return "invalid set type given to exm_put_set_param()";
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_set(int exoid, int set_type, int set_id,
              const int* set_values, const int* auxiliary)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     set_values: the set values; length is the number of objects in the set
     auxiliary: unused for EX_NODE_SET and EX_ELEM_SET; must have same length
                as 'set_values' otherwise; stores +/- orientations for
                EX_EDGE_SET and EX_FACE_SET, or local side numbers for
                EX_SIDE_SET
*/
const char* exm_put_set( int exoid, int set_type, int set_id,
                         const int* set_values, const int* auxiliary )
{
  ex_entity_type st;
  
  st = EX_NODE_SET;
  if      ( set_type == EX_NODE_SET ) { st = EX_NODE_SET; auxiliary = NULL; }
  else if ( set_type == EX_EDGE_SET ) { st = EX_EDGE_SET; }
  else if ( set_type == EX_FACE_SET ) { st = EX_FACE_SET; }
  else if ( set_type == EX_SIDE_SET ) { st = EX_SIDE_SET; }
  else if ( set_type == EX_ELEM_SET ) { st = EX_ELEM_SET; auxiliary = NULL; }
  else
    return "invalid set type given to exm_get_set()";
  
  if ( ex_put_set( exoid, st, set_id, set_values, auxiliary ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_set_dist_fact(int exoid, int set_type, int set_id, const REAL* values)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     values: the distribution factors; length is the number of objects in the
             set; the type is float if the file stores float, otherwise double
*/
const char* exm_put_set_dist_fact( int exoid, int set_type, int set_id,
                                   const void * values )
{
  ex_entity_type st;
  
  st = EX_NODE_SET;
  if      ( set_type == EX_NODE_SET ) st = EX_NODE_SET;
  else if ( set_type == EX_EDGE_SET ) st = EX_EDGE_SET;
  else if ( set_type == EX_FACE_SET ) st = EX_FACE_SET;
  else if ( set_type == EX_SIDE_SET ) st = EX_SIDE_SET;
  else if ( set_type == EX_ELEM_SET ) st = EX_ELEM_SET;
  else
    return "invalid set type given to exm_put_set_dist_fact()";
  
  if ( ex_put_set_dist_fact( exoid, st, set_id, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_map(int exoid, int map_type, int map_id, const int* map_values)
     
     exoid: an open exodus file descriptor
     map_type: one of EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP
     map_id: the target map id
     map_values: the map values; length is the number of objects in the map
*/
const char* exm_put_map( int exoid, int map_type, int map_id,
                         const int* map_values )
{
  ex_entity_type mt;
  int ierr;
  
  if      ( map_type == EX_NODE_MAP ) { mt = EX_NODE_MAP; }
  else if ( map_type == EX_EDGE_MAP ) { mt = EX_EDGE_MAP; }
  else if ( map_type == EX_FACE_MAP ) { mt = EX_FACE_MAP; }
  else if ( map_type == EX_ELEM_MAP ) { mt = EX_ELEM_MAP; }
  else
    return "invalid map type given to exm_put_map()";
  
  ierr = 0;
  if ( map_id < 0 )
  {
    if ( mt == EX_NODE_MAP )
      ierr = ex_put_node_num_map( exoid, map_values );
    else if ( mt == EX_EDGE_MAP )
      ierr = ex_put_id_map( exoid, EX_EDGE_MAP, map_values );
    else if ( mt == EX_FACE_MAP )
      ierr = ex_put_id_map( exoid, EX_FACE_MAP, map_values );
    else
      ierr = ex_put_elem_num_map( exoid, map_values );
  }
  else
    ierr = ex_put_num_map( exoid, mt, map_id, map_values );
  
  if ( ierr < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: ARGIN: namebuf
GENMOD: DOC:
  exm_put_vars(int exoid, int var_type, int num_vars, char* namebuf)
  
     exoid: an open exodus file descriptor
     var_type: one of EX_GLOBAL, EX_NODAL, EX_ELEM_BLOCK, EX_EDGE_BLOCK,
               EX_FACE_BLOCK, EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_ELEM_SET, EX_SIDE_SET, where EX_NODAL == 15
     num_vars: number of variable names to be written
     namebuf: a char buffer containing the sequence of names, each string
              must be terminated with a NUL char; the number of names must
              match the 'num_vars' value; note that the char buffer may be
              modified to restrict the name lengths to a max of MAX_STR_LENGTH
*/
const char* exm_put_vars( int exoid, int var_type, int num_vars, char* namebuf )
{
  ex_entity_type t;
  
  t = EX_GLOBAL;  /* just to avoid compiler warning */
  if      ( var_type == EX_GLOBAL     ) t = EX_GLOBAL;
  else if ( var_type == 15            ) t = EX_NODAL;
  else if ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
  else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
  else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
  else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
  else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
  else
    return "invalid var type given to exm_put_vars()";
  
  if ( num_vars >= 0 ) {
    if ( ex_put_variable_param( exoid, t, num_vars ) < 0 )
      return exm_get_error_string();
  }
  else if ( num_vars < 0 )
    return "number of variables is negative given to exm_put_vars()";
  
  if ( num_vars > 0 )
  {
    int j, slen;
    char** names;
    
    names = (char**)malloc( num_vars*sizeof(char*) );
    
    for ( j = 0; j < num_vars; ++j )
    {
      names[j] = namebuf;
      slen = strlen(namebuf);
      if ( slen > MAX_STR_LENGTH )
        namebuf[MAX_STR_LENGTH] = 0;
      namebuf += (slen+1);
    }
    
    if ( ex_put_variable_names( exoid, t, num_vars, names ) < 0 ) {
      free(names);
      return exm_get_error_string();
    }
    
    free(names);
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_truth_table(int exoid, int var_type, int num_blocks,
                      int num_vars, const int* table )
  
     exoid: an open exodus file descriptor
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     num_blocks: the number of blocks or sets stored for the var_type
     num_vars: the number of variables stored for the var_type
     table: an integer buffer of length num_blocks*num_vars containing the
            truth table values; the variable index cycles faster than the
            block index
*/
const char* exm_put_truth_table( int exoid, int var_type, int nblocks,
                                 int nvars, const int* table )
{
  ex_entity_type t;
  
  t = EX_ELEM_BLOCK;
  if      ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
  else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
  else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
  else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
  else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
  else
    return "invalid variable type given to exm_put_truth_table()";
  
  if ( nblocks > 0 && nvars > 0 ) {
    /*
      cast away const is safe here (and necessary to avoid compiler warning);
      the code in exodus/cbind/src/expvartab.c shows the array is not touched
    */
    if ( ex_put_truth_table( exoid, t, nblocks, nvars, (int*)table ) < 0 )
      return exm_get_error_string();
  }
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_time(int exoid, int time_step, const REAL* time)
  
     exoid: an open exodus file descriptor
     time_step: time steps begin at one (1)
     time: a length one array storing the floating point time value;  if the
           file stores doubles, then it must store a double, otherwise a float
*/
const char* exm_put_time( int exoid, int time_step, const void* time )
{
  if ( ex_put_time( exoid, time_step, time ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_glob_vars(int exoid, int time_step, int num_vars, const REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     num_vars: the number of global variables in the file
     values: the variable values; length must be 'num_vars'; the type
             is float if the file stores float, otherwise double
*/
const char* exm_put_glob_vars( int exoid, int time_step,
                               int num_vars, const void* values )
{
  if ( ex_put_glob_vars( exoid, time_step, num_vars, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_nodal_var(int exoid, int time_step, int var_idx,
                    int num_nodes, const REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_idx: the variable index
     num_nodes: the number of nodes in the file
     values: the variable values; length must be 'num_nodes'; the type is
             float if the file stores float, otherwise double
*/
const char* exm_put_nodal_var( int exoid, int time_step, int var_idx,
                               int num_nodes, const void* values )
{
  if ( ex_put_nodal_var( exoid, time_step, var_idx, num_nodes, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}

/*
GENMOD: DOC:
  exm_put_var(int exoid, int time_step, int var_type, int var_idx,
              int block_id, int num_objects, const REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     block_id: the id of the block or set
     num_objects: the number of objects in the block or set
     values: the variable values; length must be 'num_objects'; the type is
             float if the file stores float, otherwise double
*/
const char* exm_put_var( int exoid, int time_step, int var_type,
                         int var_idx, int block_id, int num_objects,
                         const void* values )
{
  ex_entity_type t;
  
  t = EX_ELEM_BLOCK;
  if      ( var_type == EX_ELEM_BLOCK ) t = EX_ELEM_BLOCK;
  else if ( var_type == EX_EDGE_BLOCK ) t = EX_EDGE_BLOCK;
  else if ( var_type == EX_FACE_BLOCK ) t = EX_FACE_BLOCK;
  else if ( var_type == EX_NODE_SET   ) t = EX_NODE_SET;
  else if ( var_type == EX_EDGE_SET   ) t = EX_EDGE_SET;
  else if ( var_type == EX_FACE_SET   ) t = EX_FACE_SET;
  else if ( var_type == EX_ELEM_SET   ) t = EX_ELEM_SET;
  else if ( var_type == EX_SIDE_SET   ) t = EX_SIDE_SET;
  else
    return "invalid variable type given to exm_put_var()";
  
  if ( ex_put_var( exoid, time_step, t, var_idx,
                   block_id, num_objects, values ) < 0 )
    return exm_get_error_string();
  
  return NULL;
}
