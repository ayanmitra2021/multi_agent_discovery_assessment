import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AssessmentForm from '@/components/AssessmentForm';

const makeFile = (name = 'portfolio.pdf') =>
  new File(['data'], name, { type: 'application/pdf' });

describe('AssessmentForm', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  describe('initial state', () => {
    it('renders with the submit button disabled', () => {
      render(<AssessmentForm />);
      expect(screen.getByRole('button', { name: /Start Assessment/i })).toBeDisabled();
    });

    it('shows no status banner initially', () => {
      render(<AssessmentForm />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('submit button enablement', () => {
    it('remains disabled when only a file is provided', async () => {
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      expect(screen.getByRole('button', { name: /Start Assessment/i })).toBeDisabled();
    });

    it('remains disabled when only a CSP is selected', async () => {
      render(<AssessmentForm />);
      await userEvent.click(screen.getByLabelText(/Amazon Web Services/i));
      expect(screen.getByRole('button', { name: /Start Assessment/i })).toBeDisabled();
    });

    it('becomes enabled when both file and CSP are provided', async () => {
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByLabelText(/Microsoft Azure/i));
      expect(screen.getByRole('button', { name: /Start Assessment/i })).not.toBeDisabled();
    });
  });

  describe('successful submission', () => {
    it('posts to /api/assess with file and csp in FormData', async () => {
      global.fetch = jest.fn().mockResolvedValue({ ok: true });
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByLabelText(/Google Cloud/i));
      await userEvent.click(screen.getByRole('button', { name: /Start Assessment/i }));

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/assess',
        expect.objectContaining({ method: 'POST', body: expect.any(FormData) })
      );
    });

    it('shows a success banner after a 2xx response', async () => {
      global.fetch = jest.fn().mockResolvedValue({ ok: true });
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByLabelText(/Amazon Web Services/i));
      await userEvent.click(screen.getByRole('button', { name: /Start Assessment/i }));
      await waitFor(() =>
        expect(screen.getByRole('alert')).toHaveTextContent(/Assessment submitted/i)
      );
    });
  });

  describe('failed submission', () => {
    it('shows the server error message on a non-2xx response', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ message: 'Internal Server Error' }),
      });
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByLabelText(/Microsoft Azure/i));
      await userEvent.click(screen.getByRole('button', { name: /Start Assessment/i }));
      await waitFor(() =>
        expect(screen.getByRole('alert')).toHaveTextContent(/Internal Server Error/i)
      );
    });

    it('shows a generic error when fetch throws (network failure)', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Network failure'));
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByLabelText(/Google Cloud/i));
      await userEvent.click(screen.getByRole('button', { name: /Start Assessment/i }));
      await waitFor(() =>
        expect(screen.getByRole('alert')).toHaveTextContent(/Network failure/i)
      );
    });

    it('re-enables the submit button after an error', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('fail'));
      render(<AssessmentForm />);
      await userEvent.upload(screen.getByTestId('file-input'), makeFile());
      await userEvent.click(screen.getByLabelText(/Amazon Web Services/i));
      await userEvent.click(screen.getByRole('button', { name: /Start Assessment/i }));
      await waitFor(() => screen.getByRole('alert'));
      expect(screen.getByRole('button', { name: /Start Assessment/i })).not.toBeDisabled();
    });
  });
});
