"""
바이트 변환 유틸리티

Big Endian / Little Endian 변환 함수
"""

import struct
from typing import List


# ==================== Big Endian 변환 ====================

def bytes_to_uint16_be(data: bytes) -> int:
    """
    2 bytes를 Big Endian uint16으로 변환
    
    Args:
        data: 2 bytes 데이터
    
    Returns:
        int: uint16 값 (0 ~ 65535)
    
    Example:
        >>> bytes_to_uint16_be(bytes([0x12, 0x34]))
        4660  # 0x1234
    """
    if len(data) != 2:
        raise ValueError(f"Expected 2 bytes, got {len(data)}")
    return struct.unpack('>H', data)[0]


def bytes_to_uint32_be(data: bytes) -> int:
    """
    4 bytes를 Big Endian uint32로 변환
    
    Args:
        data: 4 bytes 데이터
    
    Returns:
        int: uint32 값
    """
    if len(data) != 4:
        raise ValueError(f"Expected 4 bytes, got {len(data)}")
    return struct.unpack('>I', data)[0]


def bytes_to_uint64_be(data: bytes) -> int:
    """
    8 bytes를 Big Endian uint64로 변환
    
    Args:
        data: 8 bytes 데이터
    
    Returns:
        int: uint64 값
    """
    if len(data) != 8:
        raise ValueError(f"Expected 8 bytes, got {len(data)}")
    return struct.unpack('>Q', data)[0]


# ==================== Little Endian 변환 ====================

def bytes_to_uint16_le(data: bytes) -> int:
    """
    2 bytes를 Little Endian uint16으로 변환
    
    Args:
        data: 2 bytes 데이터
    
    Returns:
        int: uint16 값 (0 ~ 65535)
    
    Example:
        >>> bytes_to_uint16_le(bytes([0x34, 0x12]))
        4660  # 0x1234
    """
    if len(data) != 2:
        raise ValueError(f"Expected 2 bytes, got {len(data)}")
    return struct.unpack('<H', data)[0]


def bytes_to_uint32_le(data: bytes) -> int:
    """
    4 bytes를 Little Endian uint32로 변환
    
    Args:
        data: 4 bytes 데이터
    
    Returns:
        int: uint32 값
    """
    if len(data) != 4:
        raise ValueError(f"Expected 4 bytes, got {len(data)}")
    return struct.unpack('<I', data)[0]


def bytes_to_uint64_le(data: bytes) -> int:
    """
    8 bytes를 Little Endian uint64로 변환
    
    Args:
        data: 8 bytes 데이터
    
    Returns:
        int: uint64 값
    """
    if len(data) != 8:
        raise ValueError(f"Expected 8 bytes, got {len(data)}")
    return struct.unpack('<Q', data)[0]


def bytes_to_float32_le(data: bytes) -> float:
    """
    4 bytes를 Little Endian float32로 변환
    
    Args:
        data: 4 bytes 데이터
    
    Returns:
        float: float32 값
    
    Example:
        >>> import struct
        >>> data = struct.pack('<f', 3.14)
        >>> bytes_to_float32_le(data)
        3.14
    """
    if len(data) != 4:
        raise ValueError(f"Expected 4 bytes, got {len(data)}")
    return struct.unpack('<f', data)[0]


# ==================== 배열 변환 ====================

def bytes_to_uint16_array_be(data: bytes) -> List[int]:
    """
    바이트 배열을 Big Endian uint16 리스트로 변환
    
    Args:
        data: 바이트 배열 (길이는 2의 배수여야 함)
    
    Returns:
        List[int]: uint16 리스트
    
    Example:
        >>> bytes_to_uint16_array_be(bytes([0x12, 0x34, 0x56, 0x78]))
        [4660, 22136]  # [0x1234, 0x5678]
    """
    if len(data) % 2 != 0:
        raise ValueError(f"Data length must be even, got {len(data)}")
    
    count = len(data) // 2
    return list(struct.unpack(f'>{count}H', data))


def bytes_to_float32_array_le(data: bytes) -> List[float]:
    """
    바이트 배열을 Little Endian float32 리스트로 변환
    
    Args:
        data: 바이트 배열 (길이는 4의 배수여야 함)
    
    Returns:
        List[float]: float32 리스트
    """
    if len(data) % 4 != 0:
        raise ValueError(f"Data length must be multiple of 4, got {len(data)}")
    
    count = len(data) // 4
    return list(struct.unpack(f'<{count}f', data))


def bytes_to_bool_array(data: bytes) -> List[bool]:
    """
    바이트 배열을 bool 리스트로 변환
    
    각 바이트는 0(False) 또는 1(True)
    
    Args:
        data: 바이트 배열
    
    Returns:
        List[bool]: bool 리스트
    """
    return [byte != 0 for byte in data]


# ==================== 역변환 (디버깅/테스트용) ====================

def uint16_to_bytes_be(value: int) -> bytes:
    """uint16을 Big Endian 2 bytes로 변환"""
    return struct.pack('>H', value)


def uint16_to_bytes_le(value: int) -> bytes:
    """uint16을 Little Endian 2 bytes로 변환"""
    return struct.pack('<H', value)


def float32_to_bytes_le(value: float) -> bytes:
    """float32를 Little Endian 4 bytes로 변환"""
    return struct.pack('<f', value)


def bytes_to_int_auto(data: bytes, endian: str = 'big', signed: bool = False) -> int:
    """
    바이트 길이가 알려지지 않은 정수를 변환합니다 (동적 길이 지원).

    - `endian`: 'big' 또는 'little' (기본 'big')
    - `signed`: 부호 있는 정수로 해석할지 여부

    예시:
        >>> bytes_to_int_auto(b"\x01")
        1
        >>> bytes_to_int_auto(b"\x12\x34", endian='big')
        0x1234
    """
    if endian not in ('big', 'little'):
        raise ValueError("endian must be 'big' or 'little'")
    return int.from_bytes(data, byteorder=endian, signed=signed)


def bytes_to_float_auto(data: bytes, endian: str = 'little') -> float:
    """
    바이트 길이에 따라 float32 또는 float64를 자동으로 변환합니다.

    - 4 bytes -> float32
    - 8 bytes -> float64

    `endian`는 'little' 또는 'big'을 사용합니다 (기본 'little').

    예시:
        >>> import struct
        >>> data = struct.pack('<f', 3.14)
        >>> bytes_to_float_auto(data, endian='little')
        3.14
    """
    if endian not in ('big', 'little'):
        raise ValueError("endian must be 'big' or 'little'")

    if len(data) == 4:
        fmt = '<f' if endian == 'little' else '>f'
        return struct.unpack(fmt, data)[0]
    elif len(data) == 8:
        fmt = '<d' if endian == 'little' else '>d'
        return struct.unpack(fmt, data)[0]
    else:
        raise ValueError(f"Float conversion requires 4 or 8 bytes, got {len(data)}")
