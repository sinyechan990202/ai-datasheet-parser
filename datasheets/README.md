# FPGA 제어 대상 부품 문서 인덱스

모든 PDF는 제조사 공식 사이트에서 내려받았다. 별도의 레지스터 맵 문서가 없는 부품은 데이터시트 안에 레지스터 맵과 프로그래밍 절차가 포함되어 있다.

| 번호 | 부품 | 인터페이스 | 저장 문서 | 레지스터 맵 위치/상태 |
|---:|---|---|---|---|
| 1 | 25LC256 | SPI | `25AA256_25LC256_Datasheet.pdf` | 데이터시트에 명령어, 상태 레지스터, AC 타이밍 포함 |
| 2 | TMP117 | I2C/SMBus | `TMP117_Datasheet_Register_Map.pdf` | 데이터시트 7.6절에 레지스터 맵 포함 |
| 3 | INA226 | I2C | `INA226_Datasheet_Register_Map.pdf` | 데이터시트 7절에 레지스터 맵 포함 |
| 4 | ADF4351 | 3-wire SPI | `ADF4351_Datasheet_Register_Map.pdf` | 데이터시트에 6개 32-bit 레지스터 맵과 프로그래밍 순서 포함 |
| 5 | DAC80508 | SPI | `DAC80508_Datasheet_Register_Map.pdf` | 데이터시트 8.6절에 레지스터 맵 포함 |
| 6 | ADS8688 | SPI | `ADS8688_Datasheet_Register_Map.pdf` | 데이터시트 8.5절에 명령 및 프로그램 레지스터 맵 포함 |
| 7 | ADXL355 | SPI/I2C | `ADXL354_ADXL355_Datasheet_Register_Map.pdf` | 데이터시트에 직렬 인터페이스와 ADXL355 레지스터 맵 포함 |
| 8 | KSZ9031RNX | MDIO | `KSZ9031RNX_Datasheet_Register_Map.pdf` | 데이터시트 4절에 표준/MMD 레지스터 맵 포함 |
| 9 | LMK04828-EP | SPI | `LMK04828_EP_Datasheet_Register_Map.pdf` | 데이터시트에 프로그래밍 순서와 전체 레지스터 맵 포함 |
| 10 | AD9361 | SPI | `AD9361_Datasheet.pdf`, `AD9361_UG570_Reference_Manual.pdf` | 전용 레지스터 맵은 UG-671이며 아래 링크 참고 |

## AD9361 추가 문서

- UG-671 Register Map: <https://manuals.plus/m/84ad1a90d7b648798405269e872d140007d21ab867c809c972d9e3f37160a213.pdf>
- ADI 공식 제품 자료: <https://www.analog.com/en/products/ad9361.html>
- ADI 공식 No-OS 드라이버: <https://github.com/analogdevicesinc/no-OS/tree/main/drivers/rf-transceiver/ad9361>

UG-671은 ADI 공식 제품 페이지의 기존 직접 다운로드가 현재 정상 동작하지 않아 로컬 PDF로 저장하지 못했다. UG-570과 데이터시트는 공식 ADI PDF로 저장되어 있다.

## 주의사항

- 문서 버전은 다운로드 시점에 제조사 사이트에서 제공된 버전이다.
- AI 파싱 시 표뿐 아니라 reserved bit, 쓰기 순서, 지연시간, reset 조건 및 errata를 함께 처리해야 한다.
- 실제 방산 적용 등급이나 수명주기 적합성은 이 문서 모음과 별도로 QML/SMD, 온도 등급, 로트 추적성 및 승인부품목록을 확인해야 한다.
