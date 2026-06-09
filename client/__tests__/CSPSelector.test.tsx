import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CSPSelector from '@/components/CSPSelector';
import type { CSP } from '@/lib/types';

describe('CSPSelector', () => {
  it('renders all three CSP options', () => {
    render(<CSPSelector value={null} onChange={() => {}} />);
    expect(screen.getByLabelText(/Amazon Web Services/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Microsoft Azure/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Google Cloud/i)).toBeInTheDocument();
  });

  it('starts with nothing selected when value is null', () => {
    render(<CSPSelector value={null} onChange={() => {}} />);
    screen.getAllByRole('radio').forEach((r) => expect(r).not.toBeChecked());
  });

  it('checks the radio matching the current value', () => {
    render(<CSPSelector value="aws" onChange={() => {}} />);
    expect(screen.getByLabelText(/Amazon Web Services/i)).toBeChecked();
    expect(screen.getByLabelText(/Microsoft Azure/i)).not.toBeChecked();
    expect(screen.getByLabelText(/Google Cloud/i)).not.toBeChecked();
  });

  it.each<[CSP, RegExp]>([
    ['aws', /Amazon Web Services/i],
    ['azure', /Microsoft Azure/i],
    ['gcp', /Google Cloud/i],
  ])('calls onChange with "%s" when its label is clicked', async (csp, label) => {
    const onChange = jest.fn();
    render(<CSPSelector value={null} onChange={onChange} />);
    await userEvent.click(screen.getByLabelText(label));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(csp);
  });

  it('updates the checked state when value prop changes', () => {
    const { rerender } = render(<CSPSelector value="aws" onChange={() => {}} />);
    expect(screen.getByLabelText(/Amazon Web Services/i)).toBeChecked();

    rerender(<CSPSelector value="azure" onChange={() => {}} />);
    expect(screen.getByLabelText(/Microsoft Azure/i)).toBeChecked();
    expect(screen.getByLabelText(/Amazon Web Services/i)).not.toBeChecked();
  });
});
