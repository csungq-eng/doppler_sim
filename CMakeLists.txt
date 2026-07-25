cmake_minimum_required(VERSION 3.16)
project(poc_channel_doppler CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_library(channel_core
  src/rt_loader.cpp
  src/doppler_sim.cpp
)
target_include_directories(channel_core PUBLIC src)

add_executable(poc_doppler src/main.cpp)
target_link_libraries(poc_doppler PRIVATE channel_core)

enable_testing()
add_executable(unit_tests tests/test_all.cpp)
target_link_libraries(unit_tests PRIVATE channel_core)
# binary 파일 없이 실행 가능한 수식/로직 테스트. 로더 검증은 CI에서 인자로 수행.
add_test(NAME unit_tests COMMAND unit_tests)
