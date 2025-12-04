"""
단위 테스트 - 체크섬, 바이트 변환, 프레임 파싱

간단한 테스트로 구현된 모듈 검증
"""

from uart_protocol.checksum import calculate_checksum, verify_checksum
from utils.byte_converter import (
    bytes_to_uint16_be, bytes_to_uint16_le,
    bytes_to_float32_le,
    uint16_to_bytes_be, float32_to_bytes_le
)
from uart_protocol.frame_parser import FrameParser
from uart_protocol.protocol_config import STX, ETX, UartDataType


def test_checksum():
    """체크섬 테스트"""
    print("\n" + "="*50)
    print("체크섬 테스트")
    print("="*50)
    
    # 테스트 데이터
    data = bytes([0x02, 0x00, 0x04, 0x00, 0x01, 0x02, 0x03, 0x04])
    expected_checksum = 0x0010  # 2+0+4+0+1+2+3+4 = 16 (0x10)
    
    calculated = calculate_checksum(data)
    print(f"데이터: {data.hex()}")
    print(f"계산된 체크섬: 0x{calculated:04X}")
    print(f"예상 체크섬:   0x{expected_checksum:04X}")
    
    assert calculated == expected_checksum, "체크섬 불일치!"
    assert verify_checksum(data, expected_checksum), "체크섬 검증 실패!"
    
    print("✓ 체크섬 테스트 통과!")


def test_byte_conversion():
    """바이트 변환 테스트"""
    print("\n" + "="*50)
    print("바이트 변환 테스트")
    print("="*50)
    
    # uint16 Big Endian
    data_be = bytes([0x12, 0x34])
    value = bytes_to_uint16_be(data_be)
    print(f"Big Endian uint16: {data_be.hex()} → {value} (예상: 4660)")
    assert value == 0x1234, "Big Endian 변환 실패!"
    
    # uint16 Little Endian
    data_le = bytes([0x34, 0x12])
    value = bytes_to_uint16_le(data_le)
    print(f"Little Endian uint16: {data_le.hex()} → {value} (예상: 4660)")
    assert value == 0x1234, "Little Endian 변환 실패!"
    
    # float32
    original_float = 3.14159
    data_float = float32_to_bytes_le(original_float)
    converted_float = bytes_to_float32_le(data_float)
    print(f"float32: {original_float} → {data_float.hex()} → {converted_float}")
    assert abs(converted_float - original_float) < 0.0001, "float32 변환 실패!"
    
    print("✓ 바이트 변환 테스트 통과!")


# def test_frame_parser():
#     """프레임 파서 테스트"""
#     print("\n" + "="*50)
#     print("프레임 파서 테스트")
#     print("="*50)
    
#     # 샘플 프레임 생성 (ADC_BUFFER 타입, 4 bytes 페이로드)
#     stx = STX
#     data_type = UartDataType.ADC_BUFFER
#     data_length = 4
#     payload = bytes([0x01, 0x02, 0x03, 0x04])
    
#     # 체크섬 계산
#     checksum_data = bytes([stx, data_type, data_length & 0xFF, (data_length >> 8) & 0xFF]) + payload
#     checksum = calculate_checksum(checksum_data)
    
#     # 프레임 조립
#     frame_bytes = checksum_data + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF, ETX])
    
#     print(f"프레임: {frame_bytes.hex()}")
    
#     # 파서로 파싱
#     parser = FrameParser()
#     frames = parser.parse_bytes(frame_bytes)
    
#     assert len(frames) == 1, f"프레임 개수 불일치! (예상: 1, 실제: {len(frames)})"
    
#     frame = frames[0]
#     print(f"파싱된 프레임: {frame}")
#     print(f"  STX: 0x{frame.stx:02X}")
#     print(f"  타입: {frame.data_type} (ADC_BUFFER)")
#     print(f"  길이: {frame.data_length}")
#     print(f"  페이로드: {frame.payload.hex()}")
#     print(f"  체크섬: 0x{frame.checksum:04X}")
#     print(f"  ETX: 0x{frame.etx:02X}")
#     print(f"  유효: {frame.is_valid}")
    
#     assert frame.is_valid, "프레임 검증 실패!"
#     assert frame.data_type == data_type, "데이터 타입 불일치!"
#     assert frame.payload == payload, "페이로드 불일치!"
    
#     print("✓ 프레임 파서 테스트 통과!")


# def test_frame_parser_errors():
#     """프레임 파서 에러 케이스 테스트"""
#     print("\n" + "="*50)
#     print("프레임 파서 에러 케이스 테스트")
#     print("="*50)
    
#     parser = FrameParser()
    
#     # 1. STX 누락
#     print("\n1. STX 누락 테스트")
#     bad_data = bytes([0xFF, 0x00, 0x04, 0x00, 0x01, 0x02, 0x03, 0x04])
#     frames = parser.parse_bytes(bad_data)
#     print(f"  파싱된 프레임 개수: {len(frames)} (예상: 0)")
#     assert len(frames) == 0, "STX 누락 감지 실패!"
#     print("  ✓ STX 누락 정상 처리")
    
#     # 2. 체크섬 불일치
#     print("\n2. 체크섬 불일치 테스트")
#     parser.reset()
#     stx = STX
#     data_type = UartDataType.SETTINGS
#     data_length = 4
#     payload = bytes([0x01, 0x02, 0x03, 0x04])
#     wrong_checksum = 0xDEAD
#     frame_bytes = bytes([stx, data_type, data_length & 0xFF, (data_length >> 8) & 0xFF]) + payload + bytes([wrong_checksum & 0xFF, (wrong_checksum >> 8) & 0xFF, ETX])
    
#     frames = parser.parse_bytes(frame_bytes)
#     print(f"  파싱된 프레임 개수: {len(frames)} (예상: 1)")
#     assert len(frames) == 1, "프레임 파싱 자체는 성공해야 함!"
#     assert not frames[0].is_valid, "체크섬 불일치 감지 실패!"
#     print(f"  프레임 is_valid: {frames[0].is_valid} (예상: False)")
#     print("  ✓ 체크섬 불일치 정상 감지")
    
#     print("\n✓ 에러 케이스 테스트 통과!")

def test_frame_parser():
    """프레임 파서 테스트"""
    print("\n" + "="*50)
    print("프레임 파서 테스트")
    print("="*50)
    
    # 샘플 프레임 생성 (ADC_BUFFER 타입, 4 bytes 페이로드)
    from uart_protocol.protocol_config import STX_PATTERN, ETX_PATTERN
    
    stx = STX_PATTERN
    data_type = UartDataType.ADC_BUFFER
    data_length = 4
    payload = bytes([0x01, 0x02, 0x03, 0x04])
    
    # 체크섬 계산 (STX(3) + Type(1) + Length(2) + Payload)
    checksum_data = stx + bytes([data_type, data_length & 0xFF, (data_length >> 8) & 0xFF]) + payload
    checksum = calculate_checksum(checksum_data)
    
    # 프레임 조립
    frame_bytes = checksum_data + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF]) + ETX_PATTERN
    
    print(f"프레임: {frame_bytes.hex()}")
    
    # 파서로 파싱
    parser = FrameParser()
    frames = parser.parse_bytes(frame_bytes)
    
    assert len(frames) == 1, f"프레임 개수 불일치! (예상: 1, 실제: {len(frames)})"
    
    frame = frames[0]
    print(f"파싱된 프레임: {frame}")
    print(f"  STX: {frame.stx.hex().upper()}")
    print(f"  타입: {frame.data_type} (ADC_BUFFER)")
    print(f"  길이: {frame.data_length}")
    print(f"  페이로드: {frame.payload.hex()}")
    print(f"  체크섬: 0x{frame.checksum:04X}")
    print(f"  ETX: {frame.etx.hex().upper()}")
    print(f"  유효: {frame.is_valid}")
    
    assert frame.is_valid, "프레임 검증 실패!"
    assert frame.data_type == data_type, "데이터 타입 불일치!"
    assert frame.payload == payload, "페이로드 불일치!"
    
    print("✓ 프레임 파서 테스트 통과!")


def test_frame_parser_errors():
    """프레임 파서 에러 케이스 테스트"""
    print("\n" + "="*50)
    print("프레임 파서 에러 케이스 테스트")
    print("="*50)
    
    parser = FrameParser()
    from uart_protocol.protocol_config import STX_PATTERN, ETX_PATTERN
    
    # 1. STX 누락
    print("\n1. STX 누락 테스트")
    # STX 패턴(AA 55 CC)이 아닌 데이터
    bad_data = bytes([0xFF, 0x00, 0x04, 0x00, 0x01, 0x02, 0x03, 0x04])
    frames = parser.parse_bytes(bad_data)
    print(f"  파싱된 프레임 개수: {len(frames)} (예상: 0)")
    assert len(frames) == 0, "STX 누락 감지 실패!"
    print("  ✓ STX 누락 정상 처리")
    
    # 2. 체크섬 불일치
    print("\n2. 체크섬 불일치 테스트")
    parser.reset()
    stx = STX_PATTERN
    data_type = UartDataType.SETTINGS
    data_length = 4
    payload = bytes([0x01, 0x02, 0x03, 0x04])
    wrong_checksum = 0xDEAD
    
    # 프레임 조립 (잘못된 체크섬)
    frame_bytes = stx + bytes([data_type, data_length & 0xFF, (data_length >> 8) & 0xFF]) + payload + bytes([wrong_checksum & 0xFF, (wrong_checksum >> 8) & 0xFF]) + ETX_PATTERN
    
    frames = parser.parse_bytes(frame_bytes)
    print(f"  파싱된 프레임 개수: {len(frames)} (예상: 1)")
    assert len(frames) == 1, "프레임 파싱 자체는 성공해야 함!"
    assert not frames[0].is_valid, "체크섬 불일치 감지 실패!"
    print(f"  프레임 is_valid: {frames[0].is_valid} (예상: False)")
    print("  ✓ 체크섬 불일치 정상 감지")
    
    print("\n✓ 에러 케이스 테스트 통과!")

def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "="*60)
    print("iSENSOR UART Debugger - 단위 테스트")
    print("="*60)
    
    try:
        test_checksum()
        test_byte_conversion()
        test_frame_parser()
        test_frame_parser_errors()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 통과!")
        print("="*60 + "\n")
        
        return True
    
    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}\n")
        return False
    
    except Exception as e:
        print(f"\n❌ 예외 발생: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
