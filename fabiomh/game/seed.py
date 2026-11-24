"""Map seed decryption through dep/rustdecrypt.dll (`get_seed(u64, u64, u32)`).

`dw_init_seed_hash2` does not exist in ActMisc, so the same u64 at 0x840 goes as init1 and init2.
This was not verified; it is the first suspect if the seed comes out wrong.
"""
import ctypes as ct

from fabiomh.paths import RUSTDECRYPT_DLL

seed_cache = {}
rustdecrypt = None


def decrypt_seed(actMisc):
    global rustdecrypt

    init1 = int(actMisc.dw_init_seed_hash)
    init2 = int(getattr(actMisc, "dw_init_seed_hash2", actMisc.dw_init_seed_hash))
    end = int(actMisc.dw_end_seed_hash)

    # It is called every tick, so avoid reloading the DLL and recomputing the same seed
    cache_key = (init1, init2, end)
    if cache_key in seed_cache:
        return seed_cache[cache_key]

    if rustdecrypt is None:
        rustdecrypt = ct.CDLL(str(RUSTDECRYPT_DLL))

    get_seed = rustdecrypt["get_seed"]
    get_seed.argtypes = [ct.c_uint64, ct.c_uint64, ct.c_uint32]
    get_seed.restype = ct.c_uint64

    seed = int(get_seed(ct.c_uint64(init1), ct.c_uint64(init2), ct.c_uint32(end)))

    seed_cache[cache_key] = seed
    return seed
