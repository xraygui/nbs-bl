#!/usr/bin/env python3
"""
Script to modify test_regions.toml by swapping the order of energy and step values
in each region array.

The original format is: [energy1, energy2, step1, energy3, step2, ...]
The new format will be: [energy1, step1, energy2, step2, energy3, ...]
"""

import argparse
import re
from pathlib import Path


def modify_region_array(region_list):
    """
    Modify a region array by swapping the order of energy and step values.

    Parameters
    ----------
    region_list : list
        List of alternating energy and step values

    Returns
    -------
    list
        Modified list with energy and step values reordered
    """
    if len(region_list) < 3:
        return region_list  # Need at least 3 values to swap

    # The pattern is: [energy1, energy2, step1, energy3, step2, ...]
    # We want: [energy1, step1, energy2, step2, energy3, ...]

    result = [region_list[0]]  # Keep first energy value

    # Process remaining values in pairs
    for i in range(1, len(region_list) - 1, 2):
        if i + 1 < len(region_list):
            # Swap: energy, step -> step, energy
            result.append(region_list[i + 1])  # step
            result.append(region_list[i])  # energy

    return result


def modify_toml_content(content):
    """
    Modify TOML content by finding and modifying region arrays.

    Parameters
    ----------
    content : str
        Original TOML content

    Returns
    -------
    str
        Modified TOML content
    """

    # Use regex to find region arrays and modify them
    def replace_region_array(match):
        # Extract the array content
        array_str = match.group(1)

        # Parse the array values
        # Remove brackets and split by commas
        values_str = array_str.strip("[]")
        values = []

        # Simple parsing - split by comma and strip whitespace
        for val in values_str.split(","):
            val = val.strip()
            if val:
                # Try to convert to float/int, otherwise keep as string
                try:
                    if "." in val:
                        values.append(float(val))
                    else:
                        values.append(int(val))
                except ValueError:
                    values.append(val)

        # Modify the array
        modified_values = modify_region_array(values)

        # Convert back to string
        modified_str = "[" + ", ".join(str(v) for v in modified_values) + "]"
        return f"region = {modified_str}"

    # Find all region arrays and replace them
    pattern = r"region = \[([^\]]+)\]"
    modified_content = re.sub(pattern, replace_region_array, content)

    return modified_content


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Modify TOML region arrays by swapping energy and step values"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="test_regions.toml",
        help="Input TOML file path (default: test_regions.toml)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="test_regions_modified.toml",
        help="Output TOML file path (default: test_regions_modified.toml)",
    )
    return parser.parse_args()


def main():
    """Main function to process the TOML file."""
    args = parse_arguments()

    # File paths
    input_file = Path(args.input)
    output_file = Path(args.output)

    # Check if input file exists
    if not input_file.exists():
        print(f"Error: Input file {input_file} not found")
        return

    try:
        # Read the original file
        with open(input_file, "r") as f:
            content = f.read()

        print(f"Processing {input_file}...")

        # Modify the content
        modified_content = modify_toml_content(content)

        # Write the modified content
        with open(output_file, "w") as f:
            f.write(modified_content)

        print(f"Modified file written to {output_file}")

        # Show an example of the transformation
        print("\nExample transformation:")
        original_example = [1055, 1065, 1.0, 1070, 0.2, 1080, 0.1, 1100, 0.2, 1140, 1.0]
        print(f"Original: {original_example}")
        modified_example = modify_region_array(original_example)
        print(f"Modified: {modified_example}")

    except Exception as e:
        print(f"Error processing file: {e}")


if __name__ == "__main__":
    main()
