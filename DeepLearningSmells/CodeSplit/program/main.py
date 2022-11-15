import sys

from DeepLearningSmells.program.data_curation import tokenizer_runner



def main():
    tokenizer_language = 'CSharp'
    tokenizer_input_base_path = r"C:\WorkSpace\Swetha_M20AIE317_SDE_PRJ\DeepLearningSmells\data\training_data_cs"
    tokenizer_out_base_path = r'C:\WorkSpace\Swetha_M20AIE317_SDE_PRJS\DeepLearningSmells\data\tokenizer_cs1'
    tokenizer_exe_path = r'C:\WorkSpace\Swetha_M20AIE317_SDE_PRJS\tokenizer\src\tokenizer.exe'

    tokenizer_runner.tokenize(tokenizer_language, tokenizer_input_base_path, tokenizer_out_base_path, tokenizer_exe_path)


if __name__ == '__main__':
    main()
