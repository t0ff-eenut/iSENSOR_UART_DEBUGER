"""
체크섬 계산 및 검증

ESP32 펌웨어의 Sum 체크섬 방식 구현
"""


def calculate_checksum(data: bytes) -> int:
    """
    Sum 체크섬 계산 (16bit)
    
    STX부터 PAYLOAD 끝까지 모든 바이트의 합을 16bit로 제한
    
    Args:
        data: 체크섬을 계산할 바이트 배열 (STX + data_type + data_length + payload)
    
    Returns:
        int: 16bit 체크섬 값 (0x0000 ~ 0xFFFF)
    
    Example:
        >>> data = bytes([0x02, 0x00, 0x04, 0x00, 0x01, 0x02, 0x03, 0x04])
        >>> calculate_checksum(data)
        22  # 0x0016
    """
    total_sum = sum(data)
    return total_sum & 0xFFFF


def verify_checksum(frame_data: bytes, received_checksum: int) -> bool:
    """
    체크섬 검증
    
    Args:
        frame_data: 프레임 데이터 (STX ~ PAYLOAD)
        received_checksum: 수신된 체크섬 값
    
    Returns:
        bool: 체크섬이 일치하면 True, 불일치하면 False
    
    Example:
        >>> frame = bytes([0x02, 0x00, 0x04, 0x00, 0x01, 0x02, 0x03, 0x04])
        >>> verify_checksum(frame, 0x0016)
        True
    """
    calculated = calculate_checksum(frame_data)
    return calculated == received_checksum


def calculate_checksum_with_details(data: bytes) -> dict:
    """
    상세 정보와 함께 체크섬 계산 (디버깅용)
    
    Args:
        data: 체크섬을 계산할 바이트 배열
    
    Returns:
        dict: {
            'checksum': 체크섬 값,
            'total_sum': 전체 합,
            'data_length': 데이터 길이,
            'hex': 16진수 문자열
        }
    """
    total_sum = sum(data)
    checksum = total_sum & 0xFFFF
    
    return {
        'checksum': checksum,
        'total_sum': total_sum,
        'data_length': len(data),
        'hex': f'0x{checksum:04X}'
    }
