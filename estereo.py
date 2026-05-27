"""
Laia March Cervantes

Fitxer estereo.py: Conté funcions per a la manipulació de fitxers WAVE,
incloent la conversió entre mono/estèreo i codificació de 32 bits.
"""

import struct

def leer_cabecera(f):
    """
    Desempaqueta la cabecera d'un fitxer WAVE i valida el seu format.
    """
    try:
        riff, size, wave = struct.unpack('<4sI4s', f.read(12))
        if riff != b'RIFF' or wave != b'WAVE':
            raise ValueError("El fitxer no és un format WAVE vàlid.")

        fmt_id, fmt_size = struct.unpack('<4sI', f.read(8))
        if fmt_id != b'fmt ':
            raise ValueError("No s'ha trobat el subcacho 'fmt '.")
        
        # PCM lineal té normalment 16 bytes de dades en el subcacho fmt
        fmt_data = struct.unpack('<HHIIHH', f.read(16))
        if fmt_size > 16:
            f.read(fmt_size - 16)

        data_id, data_size = struct.unpack('<4sI', f.read(8))
        while data_id != b'data':
            f.read(data_size)
            data_id, data_size = struct.unpack('<4sI', f.read(8))

        return {
            'canals': fmt_data[2],
            'freq': fmt_data[6],
            'byte_rate': fmt_data[7],
            'block_align': fmt_data[8],
            'bits_per_sample': fmt_data[9],
            'data_size': data_size
        }
    except struct.error:
        raise ValueError("Error en llegir l'estructura de la cabecera.")

def escribir_cabecera(f, params, num_muestras):
    """
    Empaqueta i escriu la cabecera WAVE correctament per a la seva reproducció.
    """
    bytes_per_sample = params['bits_per_sample'] // 8
    data_size = num_muestras * bytes_per_sample * params['canals']
    
    f.write(struct.pack('<4sI4s', b'RIFF', data_size + 36, b'WAVE'))
    f.write(struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, params['canals'], 
                        params['freq'], params['byte_rate'], 
                        params['block_align'], params['bits_per_sample']))
    f.write(struct.pack('<4sI', b'data', data_size))

def estereo2mono(ficEste, ficMono, canal=2):
    """Converteix estèreo a mono: 0=L, 1=R, 2=Semisuma, 3=Semidiferència."""
    with open(ficEste, 'rb') as f_in, open(ficMono, 'wb') as f_out:
        p = leer_cabecera(f_in)
        if p['canals'] != 2:
            raise ValueError("El fitxer d'entrada ha de ser estèreo.")
        
        num_m = p['data_size'] // p['block_align']
        dades = struct.unpack(f'<{num_m * 2}h', f_in.read(p['data_size']))
        L, R = dades[::2], dades[1::2]
        
        opcions = {
            0: L,
            1: R,
            2: [(l + r) // 2 for l, r in zip(L, R)],
            3: [(l - r) // 2 for l, r in zip(L, R)]
        }
        res = opcions.get(canal)
        if res is None: raise ValueError("Canal no vàlid.")
            
        p.update({'canals': 1, 'block_align': p['bits_per_sample'] // 8})
        p['byte_rate'] = p['freq'] * p['block_align']
        escribir_cabecera(f_out, p, num_m)
        f_out.write(struct.pack(f'<{num_m}h', *res))

def mono2estereo(ficIzq, ficDer, ficEste):
    """Combina dos fitxers mono en un d'estèreo."""
    with open(ficIzq, 'rb') as f_l, open(ficDer, 'rb') as f_r, open(ficEste, 'wb') as f_out:
        p_l, p_r = leer_cabecera(f_l), leer_cabecera(f_r)
        num_m = min(p_l['data_size'] // p_l['block_align'], p_r['data_size'] // p_r['block_align'])
        
        L = struct.unpack(f'<{num_m}h', f_l.read(num_m * (p_l['bits_per_sample'] // 8)))
        R = struct.unpack(f'<{num_m}h', f_r.read(num_m * (p_r['bits_per_sample'] // 8)))
        
        intercalat = [val for parella in zip(L, R) for val in parella]
        p_l.update({'canals': 2, 'block_align': (p_l['bits_per_sample'] // 8) * 2})
        p_l['byte_rate'] = p_l['freq'] * p_l['block_align']
        
        escribir_cabecera(f_out, p_l, num_m)
        f_out.write(struct.pack(f'<{num_m * 2}h', *intercalat))

def codEstereo(ficEste, ficCod):
    """Codifica a 32 bits: MSB = (L+R)/2, LSB = (L-R)/2."""
    with open(ficEste, 'rb') as f_in, open(ficCod, 'wb') as f_out:
        p = leer_cabecera(f_in)
        num_m = p['data_size'] // p['block_align']
        dades = struct.unpack(f'<{num_m * 2}h', f_in.read(p['data_size']))
        
        cod = [(((l + r) // 2) << 16) | (((l - r) // 2) & 0xFFFF) 
               for l, r in zip(dades[::2], dades[1::2])]
        
        p.update({'canals': 1, 'bits_per_sample': 32, 'block_align': 4})
        p['byte_rate'] = p['freq'] * 4
        escribir_cabecera(f_out, p, num_m)
        f_out.write(struct.pack(f'<{num_m}i', *cod))

def decEstereo(ficCod, ficEste):
    """Decodifica el senyal de 32 bits a estèreo de 16 bits."""
    with open(ficCod, 'rb') as f_in, open(ficEste, 'wb') as f_out:
        p = leer_cabecera(f_in)
        num_m = p['data_size'] // p['block_align']
        dades = struct.unpack(f'<{num_m}i', f_in.read(p['data_size']))
        
        semisuma = [v >> 16 for v in dades]
        semidif = [((v & 0xFFFF) ^ 0x8000) - 0x8000 for v in dades]
        
        L = [s + d for s, d in zip(semisuma, semidif)]
        R = [s - d for s, d in zip(semisuma, semidif)]
        inter = [val for parella in zip(L, R) for val in parella]
        
        p.update({'canals': 2, 'bits_per_sample': 16, 'block_align': 4})
        p['byte_rate'] = p['freq'] * 4
        escribir_cabecera(f_out, p, num_m)
        f_out.write(struct.pack(f'<{num_m * 2}h', *inter))