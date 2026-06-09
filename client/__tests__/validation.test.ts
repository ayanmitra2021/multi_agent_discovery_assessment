import { validateFile } from '@/lib/validation';

const makeFile = (name: string, sizeBytes = 1024) =>
  new File(['x'.repeat(sizeBytes)], name, { type: 'application/octet-stream' });

describe('validateFile', () => {
  describe('accepted file types', () => {
    it.each(['.pdf', '.docx', '.xlsx', '.csv'])('accepts %s files', (ext) => {
      expect(validateFile(makeFile(`portfolio${ext}`))).toEqual({ valid: true });
    });

    it('is case-insensitive for extensions', () => {
      expect(validateFile(makeFile('report.PDF'))).toEqual({ valid: true });
      expect(validateFile(makeFile('data.XLSX'))).toEqual({ valid: true });
      expect(validateFile(makeFile('intake.Docx'))).toEqual({ valid: true });
    });
  });

  describe('rejected file types', () => {
    it.each(['.txt', '.png', '.zip', '.exe', '.json', '.pptx'])(
      'rejects %s with an informative error',
      (ext) => {
        const result = validateFile(makeFile(`file${ext}`));
        expect(result.valid).toBe(false);
        expect(result.error).toMatch(/Unsupported file type/i);
      }
    );

    it('rejects files with no extension', () => {
      const result = validateFile(makeFile('nodotfile'));
      expect(result.valid).toBe(false);
    });
  });

  describe('size validation', () => {
    const MB = 1024 * 1024;

    it('accepts files well under the 25 MB limit', () => {
      expect(validateFile(makeFile('small.pdf', 1 * MB))).toEqual({ valid: true });
    });

    it('accepts files exactly at 25 MB', () => {
      expect(validateFile(makeFile('exact.pdf', 25 * MB))).toEqual({ valid: true });
    });

    it('rejects files over 25 MB', () => {
      const result = validateFile(makeFile('big.pdf', 25 * MB + 1));
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/25 MB/);
    });

    it('includes the limit in the error message', () => {
      const result = validateFile(makeFile('huge.xlsx', 30 * MB));
      expect(result.error).toContain('25 MB');
    });
  });
});
