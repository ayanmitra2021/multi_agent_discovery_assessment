import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileUpload from '@/components/FileUpload';

// Minimal-content file — use for type-based tests
const makeFile = (name = 'portfolio.pdf', type = 'application/pdf') =>
  new File(['content'], name, { type });

// Real file with a mocked size property — avoids allocating large strings
const makeFileWithSize = (name: string, sizeBytes: number) => {
  const file = new File(['x'], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'size', { value: sizeBytes });
  return file;
};

// Fires the change event directly, bypassing the input's `accept` filter.
// Needed for testing files that wouldn't pass the browser's native accept filter.
const uploadViaEvent = (input: HTMLElement, file: File) => {
  fireEvent.change(input, { target: { files: [file] } });
};

describe('FileUpload', () => {
  describe('initial state', () => {
    it('renders the upload prompt', () => {
      render(<FileUpload onFileChange={() => {}} />);
      expect(screen.getByText(/Click to upload/i)).toBeInTheDocument();
      expect(screen.getByText(/PDF, DOCX, XLSX, CSV/i)).toBeInTheDocument();
    });

    it('has a hidden file input accepting the correct formats', () => {
      render(<FileUpload onFileChange={() => {}} />);
      const input = screen.getByTestId('file-input');
      expect(input).toHaveAttribute('accept', '.pdf,.docx,.xlsx,.csv');
    });
  });

  describe('valid file selection', () => {
    it('shows the file name after a valid upload', async () => {
      render(<FileUpload onFileChange={() => {}} />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile('report.pdf'));
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    it('calls onFileChange with the File object for a valid file', async () => {
      const onFileChange = jest.fn();
      render(<FileUpload onFileChange={onFileChange} />);
      const file = makeFile('data.xlsx');
      await userEvent.upload(screen.getByTestId('file-input'), file);
      expect(onFileChange).toHaveBeenCalledWith(file);
    });

    it('shows a Remove button after file selection', async () => {
      render(<FileUpload onFileChange={() => {}} />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      expect(screen.getByRole('button', { name: /Remove file/i })).toBeInTheDocument();
    });
  });

  describe('invalid file selection', () => {
    it('shows a validation error for unsupported file types', () => {
      render(<FileUpload onFileChange={() => {}} />);
      uploadViaEvent(
        screen.getByTestId('file-input'),
        new File(['data'], 'script.exe', { type: 'application/x-msdownload' })
      );
      expect(screen.getByRole('alert')).toHaveTextContent(/Unsupported file type/i);
    });

    it('calls onFileChange(null) when file type is invalid', () => {
      const onFileChange = jest.fn();
      render(<FileUpload onFileChange={onFileChange} />);
      uploadViaEvent(
        screen.getByTestId('file-input'),
        new File(['data'], 'image.png', { type: 'image/png' })
      );
      expect(onFileChange).toHaveBeenCalledWith(null);
    });

    it('shows a size error when file exceeds 25 MB', () => {
      render(<FileUpload onFileChange={() => {}} />);
      uploadViaEvent(
        screen.getByTestId('file-input'),
        makeFileWithSize('big.pdf', 26 * 1024 * 1024)
      );
      expect(screen.getByRole('alert')).toHaveTextContent(/25 MB/i);
    });
  });

  describe('remove file', () => {
    it('clears the file name when Remove is clicked', async () => {
      render(<FileUpload onFileChange={() => {}} />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile('data.csv'));
      await userEvent.click(screen.getByRole('button', { name: /Remove file/i }));
      expect(screen.queryByText('data.csv')).not.toBeInTheDocument();
    });

    it('calls onFileChange(null) when Remove is clicked', async () => {
      const onFileChange = jest.fn();
      render(<FileUpload onFileChange={onFileChange} />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile('data.csv'));
      await userEvent.click(screen.getByRole('button', { name: /Remove file/i }));
      expect(onFileChange).toHaveBeenLastCalledWith(null);
    });

    it('shows the upload prompt again after removal', async () => {
      render(<FileUpload onFileChange={() => {}} />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByRole('button', { name: /Remove file/i }));
      expect(screen.getByText(/Click to upload/i)).toBeInTheDocument();
    });
  });

  describe('drag and drop', () => {
    it('applies active styling on dragenter', () => {
      render(<FileUpload onFileChange={() => {}} />);
      const zone = screen.getByRole('button', { name: /Upload file/i });
      fireEvent.dragEnter(zone);
      expect(zone.className).toContain('border-blue-500');
    });

    it('removes active styling on dragleave', () => {
      render(<FileUpload onFileChange={() => {}} />);
      const zone = screen.getByRole('button', { name: /Upload file/i });
      fireEvent.dragEnter(zone);
      fireEvent.dragLeave(zone);
      expect(zone.className).not.toContain('border-blue-500');
    });
  });
});
