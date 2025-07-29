"""
Common utilities used by other openeo modules.
"""

import logging

def get_nested_default(cfg_dict, path, default_key=None):
    """Navigate a dictionary using a provided path tuple.  If any key in the path
    doesn't exist, return the default value instead."""
    # print("get_nested_default(%s,%s,%s)" % (repr(cfg_dict), repr(path), repr(default_key)))
    if not isinstance(path, tuple) and not isinstance(path, list):
        raise TypeError("invalid path type")
    try:
        # Reached requested depth?  Return the data, whatever it may be.
        if len(path) == 1:
            return cfg_dict[path[0]]
        else:
            # Keep searching
            inner = cfg_dict[path[0]]
            new_path = tuple(path[1:])
            if not isinstance(inner, dict):
                if len(path) > 1:
                    # There are more keys in the path than keys remaining, which means
                    # the key doesn't exist.
                    return default_key
                else:
                    return inner
            else:
                return get_nested_default(inner, new_path, default_key)
    except KeyError:
        return default_key

def add_simple_setting(config, context, type, root_module, path, name, default="", note="", range=(), step=1, pattern="", value_unit=""):
    path_joined = ":".join([root_module] + list(path))
    print("%r -> %r" % ((config, path, default), get_nested_default(config, path, default)))
    
    context.append({ 
        'type'        : type, 
        'id'          : path_joined,
        'value'       : get_nested_default(config, path, default), 
        'name'        : name, 
        'note'        : note, 
        'range'       : range, 
        'step'        : step, 
        'root_module' : root_module,
        'pattern'     : pattern, 
        'value_unit'  : value_unit })

def add_header_setting(context, heading_text):
    context.append({ 'type' : 'heading', 'text' : heading_text })

def add_category_exit(context):
    context.append({ 'type' : 'catend' })

def TEST_get_nested_default():
    # Test cases
    cfg_dict = {
        "abc" : { "def" : 123, "ghi" : { "jkl" : 456, "mno" : 789 } },
        "pqr" : 234
    }
    
    print("Running assertion tests")
    
    # Keys that exist.
    assert(get_nested_default(cfg_dict, ("abc",), None) == cfg_dict["abc"])
    assert(get_nested_default(cfg_dict, ("abc", "def"), None) == cfg_dict["abc"]["def"])
    assert(get_nested_default(cfg_dict, ("abc", "ghi"), None) == cfg_dict["abc"]["ghi"])
    assert(get_nested_default(cfg_dict, ("abc", "ghi", "jkl"), None) == cfg_dict["abc"]["ghi"]["jkl"])
    assert(get_nested_default(cfg_dict, ("abc", "ghi", "mno"), None) == cfg_dict["abc"]["ghi"]["mno"])
    assert(get_nested_default(cfg_dict, ("pqr",), None) == cfg_dict["pqr"])
    
    # Lists are permitted in the path.
    assert(get_nested_default(cfg_dict, ["abc"], None) == cfg_dict["abc"])
    assert(get_nested_default(cfg_dict, ["abc", "def"], None) == cfg_dict["abc"]["def"])
    assert(get_nested_default(cfg_dict, ["abc", "ghi"], None) == cfg_dict["abc"]["ghi"])
    
    # Keys that don't exist, and a default value should be returned.
    assert(get_nested_default(cfg_dict, ("jjj",), 999) == 999)
    assert(get_nested_default(cfg_dict, ("ppp",), True) == True)
    assert(get_nested_default(cfg_dict, ("mmm", "def"), 200) == 200)
    assert(get_nested_default(cfg_dict, ("abc", "ccc", "jjj"), 300) == 300)
    assert(get_nested_default(cfg_dict, ("abc", "ghi", "mno", "pqr"), 400) == 400)
    
    # Invalid tuples.  Should raise exceptions.
    try:
        get_nested_default(cfg_dict, "NotATuple", 999) == 999
    except Exception:
        print("Passed exception")
    else:
        raise AssertionError("Failed exception test")
        
    try:
        get_nested_default(cfg_dict, None, 999) == 999
    except Exception:
        print("Passed exception")
    else:
        raise AssertionError("Failed exception test")
    
    print("Tests complete")

if __name__ == "__main__":
    TEST_get_nested_default()