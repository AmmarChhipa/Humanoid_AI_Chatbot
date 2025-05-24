def add_three_numbers(num1, num2, num3):
  """
  This function takes three numbers as input and returns their sum.
  Args:
    num1: The first number.
    num2: The second number.
    num3: The third number.
  Returns:
    The sum of the three numbers.
  """
  sum_of_numbers = num1 + num2 + num3
  return sum_of_numbers
# Example usage:
number1 = 10
number2 = 20
number3 = 30
result = add_three_numbers(number1, number2, number3)
print(f"The sum of {number1}, {number2}, and {number3} is: {result}")
