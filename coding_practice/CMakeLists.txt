cmake_minimum_required(VERSION 3.10)

project(CS300_Coding_Practice LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(chapter_three ch_3.cpp)
add_executable(VectorSorting 
    assignments/VectorSorting/VectorSorting.cpp
    assignments/VectorSorting/CSVparser.cpp
    )