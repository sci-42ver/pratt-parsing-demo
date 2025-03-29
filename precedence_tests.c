#include<stdio.h>
int main(){
  int a=0;
  printf("%d,%d\n",2>1?a=3:(a=2),a);
  printf("%d,%d\n",2<1?a=3:(a=2),a);
}