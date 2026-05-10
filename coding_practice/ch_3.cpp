#include <iostream>
#include <stdlib.h>
#include <string>
#include <vector>
#include <algorithm>

void DisplayTopFiveSalespersons(const std::vector<Salesperson>& allSalespersons);


int main() {
    std::printf("hello c++\n\n");

    // Record: the data structure that stores subitems, often called fields, with a name associted with each subitem

    // Array: data structure that stores an ordered list of items

    // Linked List: stores an ordered list of items in nodes, where each node stores data and has a pointer to the next node

    // Binary Tree: data structure in which each node stores data and has up to two children, known as a left and right child

    // Hash table: data structure that stores unordered items by mapping each item to a location in an array

    // Heap: is a tree that maintains the simple property that a node's key is greater than or equal to the node's childrens' keys. 

    // Min-Heap: is a tree that maintains the simple property that a node's key is less than or equal to the node's childrens' keys

    // Graph: A graph is a data structure for representing connections amoung items and consits of vertices connected by edges.


    std::vector<Salesperson> people = {
        {"Alice", 5200}, {"Bob", 7800}, {"Carol", 3100},
        {"Dave", 9100}, {"Eve", 4400}, {"Frank", 6700},
        {"Grace", 8500}
    };
    DisplayTopFiveSalespersons(people);


    // ADT: abstract data type is a data type described by predefined user operations, such as as "insert data at rear" without
    //  indicating how each operation is implemented.

    // List: an ADT for holding ordered data.

    // Dynamic Array: an ADT for holding ordered data and allow indexed access.

    // Stack: an ADT in which items are only inserted on or removed from the top of a stack.

    // Queue: an ADT in which items are inserted at the end of the queue and removed from the front of the queue.

    // Deque: an ADT in which items can be inserted and removed at both the front an and back.

    // Bag: an ADT for storing items in which the order does not matter and duplicate items are allowed.

    // Set: an ADT for a collection of distinct items.

    // Priority Queue: a queue where each item has a priority, and items with higher priority are closer to the front of the 
    //  queue than items with lower priority.

    // Dictionary (MAP): an ADT that associates (or maps) keys with values

    

}

/* Algorithm to determin top file salespersons using an array*/
struct Salesperson {
    std::string name;
    double salesTotal;
};

void DisplayTopFiveSalespersons(const std::vector<Salesperson>& allSalespersons) {
    // topSales has 5 elements, kept sorted highest -> lowest
    std::vector<Salesperson> topSales(5, {"", -1.0});

    for (const auto& salesPerson : allSalespersons) {
        // If this person beats the smallest of the current top 5, they're in
        if (salesPerson.salesTotal > topSales.back().salesTotal) {
            topSales.back() = salesPerson;

            // Re-sort descending
            std::sort(topSales.begin(), topSales.end(),
                [](const Salesperson& a, const Salesperson& b) {
                    return a.salesTotal > b.salesTotal;
                });
        }
    }

    for (const auto& sp : topSales) {
        if (sp.salesTotal >= 0) {
            std::cout << sp.name << ": " << sp.salesTotal << "\n";
        }
    }
}
