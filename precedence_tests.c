#include<stdio.h>
#include <stdbool.h>
int main(){
  int a=0;
  printf("%d,%d\n",2>1?a=3:(a=2),a);
  printf("%d,%d\n",2<1?a=3:(a=2),a);

  bool b=false;
  // For c++, https://cs.nyu.edu/courses/fall11/CSCI-GA.2110-003/documents/c%2B%2B2003std.pdf p99.
  // > except that the operand shall not be of type bool.
  // because the behavior will have implicit underflow.
  // For c, compiler ensures no underflow/overflow for bool, so no problems in https://stackoverflow.com/a/3450592/21294350.
  // > overflow can't happen until I've done ++ often enough to cause an overflow on it's own.
  printf("%d\n",b--);
  // 0
  printf("%d\n",b--);
  // 1
  printf("%d\n",b--);
  // 0

  printf("b++:\n");
  // All 1.
  printf("%d\n",b++);
  printf("%d\n",b++);
}