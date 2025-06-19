import json

import pandas as pd


class FileHandler:
    @classmethod
    def read_file(cls, filename: str, **kwargs) -> pd.DataFrame:
        df = pd.read_csv(filename, **kwargs)
        return df

    @classmethod
    def write_file(cls, filename: str, df: pd.DataFrame, **kwargs) -> None:
        df.to_csv(filename, **kwargs)

    @classmethod
    def read_json(cls, filename, **kwargs) -> dict:
        with open(filename, 'r') as json_file:
            return json.load(json_file, **kwargs)

    @classmethod
    def write_json(cls, filename, df: dict, **kwargs) -> None:
        with open(filename, 'w') as json_file:
            json.dump(df, json_file, **kwargs)