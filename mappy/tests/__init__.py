import os
import numpy as np
import unittest
from qgis.core import QgsApplication
app = QgsApplication([], True)
app.initQgis()
print(app)


class ExtendedUnitTesting(unittest.TestCase):

    @staticmethod
    def clean_up(clean_up_files):
        for file in clean_up_files:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except PermissionError:
                    pass

    def assertEqualFloatArray(self, array1, array2, decimals):
        if array1.ndim == 1:
            pix = array1.shape[0]
        elif array1.ndim == 2:
            pix = array1.shape[0] * array1.shape[1]
        elif array1.ndim == 3:
            pix = array1.shape[0] * array1.shape[1] * array1.shape[2]
        else:
            assert 0

        array1_line = np.reshape(array1, pix)
        array2_line = np.reshape(array2, pix)
        for i in range(pix):
            self.assertAlmostEqual(array1_line[i], array2_line[i], places=decimals)

    def assertEqualIntArray(self, array1, array2):
        if array1.ndim == 1:
            pix = array1.shape[0]
        elif array1.ndim == 2:
            pix = array1.shape[0] * array1.shape[1]
        elif array1.ndim == 3:
            pix = array1.shape[0] * array1.shape[1] * array1.shape[2]
        else:
            assert 0

        array1_line = np.reshape(array1, pix)
        array2_line = np.reshape(array2, pix)
        for i in range(pix):
            self.assertEqual(array1_line[i], array2_line[i])

    def assertEqualStringArray(self, array1, array2):
        x = array1.shape[0]
        for i in range(x):
            self.assertEqual(array1[i], array2[i])

    def assertFileExists(self, path):
        from pathlib import Path
        self.assertIs(Path(path).exists(), True)
