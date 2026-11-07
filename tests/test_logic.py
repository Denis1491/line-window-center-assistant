import unittest

from line_window_center import centered_position, fitted_size, fits_with_margin, has_student_date, is_relevant_window


class WindowLogicTests(unittest.TestCase):
    def test_dates_are_valid_and_complete(self):
        self.assertTrue(has_student_date("測試學員1120706"))
        self.assertTrue(has_student_date("學員1141231"))
        for title in ("LINE", "學員1120230", "學員1121301", "12311207061"):
            self.assertFalse(has_student_date(title))

    def test_center_respects_work_area(self):
        self.assertEqual(centered_position((0, 0, 1920, 1032), 400, 600), (760, 216))
        self.assertEqual(centered_position((-1000, 20, 0, 820), 400, 600), (-700, 120))

    def test_line_windows_include_keep_and_owned_dialogs(self):
        self.assertTrue(is_relevant_window("Keep筆記", False, 585, 845))
        self.assertTrue(is_relevant_window("LINE", True, 352, 552))
        self.assertTrue(is_relevant_window("", True, 352, 552))
        self.assertFalse(is_relevant_window("", False, 352, 552))
        self.assertFalse(is_relevant_window("LINE", True, 30, 30))

    def test_large_window_leaves_space_for_frame(self):
        self.assertEqual(fitted_size((0, 0, 1920, 1032), 566, 1032), (566, 1000))
        self.assertEqual(fitted_size((0, 0, 1920, 1032), 352, 552), (352, 552))
        self.assertTrue(fits_with_margin((100, 16, 666, 1016), (0, 0, 1920, 1032)))
        self.assertFalse(fits_with_margin((100, 0, 666, 1032), (0, 0, 1920, 1032)))


if __name__ == "__main__":
    unittest.main()

